from datetime import UTC, datetime
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

from app.workers import payment_fulfillment


def test_worker_delivers_fulfillment() -> None:
    fake_fulfillment = SimpleNamespace(
        id=900001,
        payment_id=900001,
        attempts=1,
    )

    fake_user = SimpleNamespace(
        telegram_id=995500001,
    )

    fake_payment = SimpleNamespace(
        id=900001,
    )

    fake_subscription = SimpleNamespace(
        expires_at=datetime(
            2026,
            12,
            31,
            23,
            59,
            tzinfo=UTC,
        ),
    )

    fake_device = SimpleNamespace(
        id=800001,
        device_name="Основное устройство",
    )

    fake_vless = (
        "vless://11111111-2222-3333-4444-555555555555"
        "@vpn.example.com:443"
        "?type=tcp&security=reality"
    )

    fake_token = SimpleNamespace(
        id=1,
        user_id=123,
        version=1,
    )

    fake_raw_token = (
        "123.1."
        "abcdefghijklmnopqrstuvwxyz0123456789ABCDE"
    )

    expected_connect_url = (
        f"{payment_fulfillment.settings.connect_base_url.rstrip('/')}/"
        f"{fake_raw_token}"
    )

    with patch(
        "app.workers.payment_fulfillment."
        "payment_fulfillment_service.recover_stale_processing",
        return_value=0,
    ), patch(
        "app.workers.payment_fulfillment."
        "payment_fulfillment_service.claim_next",
        return_value=fake_fulfillment,
    ), patch(
        "app.workers.payment_fulfillment."
        "payment_fulfillment_service.build_access",
        return_value=(
            fake_user,
            fake_payment,
            fake_subscription,
            fake_device,
            fake_vless,
        ),
    ) as build_access, patch(
        "app.workers.payment_fulfillment."
        "subscription_token_service.get_or_create_token",
        return_value=(
            fake_token,
            fake_raw_token,
        ),
    ) as get_token, patch(
        "app.workers.payment_fulfillment."
        "send_telegram_message"
    ) as send_message, patch(
        "app.workers.payment_fulfillment."
        "payment_fulfillment_service.mark_delivered"
    ) as mark_delivered:
        result = payment_fulfillment.process_once()

    assert result is True

    build_access.assert_called_once()
    get_token.assert_called_once()

    token_kwargs = get_token.call_args.kwargs
    assert token_kwargs["telegram_id"] == 995500001

    send_message.assert_called_once()

    telegram_call = send_message.call_args.kwargs

    assert telegram_call["telegram_id"] == 995500001
    assert telegram_call["connect_url"] == expected_connect_url

    message_text = telegram_call["text"]

    assert "Оплата получена" in message_text
    assert "Work&PlayVPN" in message_text
    assert "31.12.2026" in message_text
    assert "Основное устройство" in message_text
    assert "VPN готов к подключению" in message_text

    # Технические ссылки больше не показываем в тексте.
    assert fake_vless not in message_text
    assert fake_raw_token not in message_text
    assert expected_connect_url not in message_text
    assert "vless://" not in message_text

    mark_delivered.assert_called_once()

    delivered_kwargs = mark_delivered.call_args.kwargs

    assert delivered_kwargs["fulfillment"] is fake_fulfillment


def test_send_telegram_message_builds_connect_button() -> None:
    fake_response = SimpleNamespace(
        status_code=200,
        json=lambda: {"ok": True},
    )

    fake_client = MagicMock()
    fake_client.__enter__.return_value = fake_client
    fake_client.__exit__.return_value = None
    fake_client.post.return_value = fake_response

    connect_url = (
        "https://connect.test.local/connect/happ/"
        "123.1.test-token"
    )

    proxy_url = "socks5://telegram-egress:1080"

    with patch.object(
        payment_fulfillment.settings,
        "telegram_bot_token",
        "test-telegram-bot-token",
    ), patch.object(
        payment_fulfillment.settings,
        "telegram_proxy_url",
        proxy_url,
    ), patch(
        "app.workers.payment_fulfillment.httpx.Client",
        return_value=fake_client,
    ) as http_client:
        payment_fulfillment.send_telegram_message(
            telegram_id=995500001,
            text="VPN готов к подключению.",
            connect_url=connect_url,
        )

    http_client.assert_called_once_with(
        proxy=proxy_url,
        timeout=15.0,
    )

    fake_client.post.assert_called_once()

    args, kwargs = fake_client.post.call_args

    assert args[0] == (
        "https://api.telegram.org/"
        "bottest-telegram-bot-token/sendMessage"
    )

    payload = kwargs["json"]

    assert payload["chat_id"] == 995500001
    assert payload["text"] == "VPN готов к подключению."
    assert payload["disable_web_page_preview"] is True

    keyboard = payload["reply_markup"]["inline_keyboard"]

    assert len(keyboard) == 1
    assert len(keyboard[0]) == 1

    button = keyboard[0][0]

    assert button["text"] == "🚀 Подключить VPN"
    assert button["url"] == connect_url


def test_worker_marks_failed_when_delivery_raises() -> None:
    fake_fulfillment = SimpleNamespace(
        id=700001,
        payment_id=700001,
        attempts=1,
    )

    with patch(
        "app.workers.payment_fulfillment."
        "payment_fulfillment_service.recover_stale_processing",
        return_value=0,
    ), patch(
        "app.workers.payment_fulfillment."
        "payment_fulfillment_service.claim_next",
        return_value=fake_fulfillment,
    ), patch(
        "app.workers.payment_fulfillment."
        "payment_fulfillment_service.build_access",
        side_effect=RuntimeError("temporary failure"),
    ), patch(
        "app.workers.payment_fulfillment."
        "payment_fulfillment_service.mark_failed"
    ) as mark_failed:
        result = payment_fulfillment.process_once()

    assert result is True

    mark_failed.assert_called_once()

    kwargs = mark_failed.call_args.kwargs

    assert kwargs["fulfillment"] is fake_fulfillment
    assert kwargs["error"] == "temporary failure"


def test_worker_returns_false_when_no_pending_fulfillment() -> None:
    with patch(
        "app.workers.payment_fulfillment."
        "payment_fulfillment_service.recover_stale_processing",
        return_value=0,
    ), patch(
        "app.workers.payment_fulfillment."
        "payment_fulfillment_service.claim_next",
        return_value=None,
    ):
        result = payment_fulfillment.process_once()

    assert result is False