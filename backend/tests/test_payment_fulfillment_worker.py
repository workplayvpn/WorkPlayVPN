from datetime import UTC, datetime
from types import SimpleNamespace
from unittest.mock import patch

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

    expected_subscription_url = (
        f"{payment_fulfillment.settings.subscription_base_url.rstrip('/')}/"
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

    message_text = telegram_call["text"]

    assert "Оплата получена" in message_text
    assert "Work&PlayVPN" in message_text
    assert "31.12.2026" in message_text
    assert "Основное устройство" in message_text
    assert expected_subscription_url in message_text

    # Сырой VLESS пользователю больше не отправляем.
    assert fake_vless not in message_text

    mark_delivered.assert_called_once()

    delivered_kwargs = mark_delivered.call_args.kwargs

    assert delivered_kwargs["fulfillment"] is fake_fulfillment


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