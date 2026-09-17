import httpx
from aiogram import F, Router
from aiogram.types import CallbackQuery

from api.backend import (
    backend_get,
    backend_post,
)
from ui.common import build_back_to_main_keyboard
from ui.main import main_menu
from ui.payments import (
    build_payment_confirmation_keyboard,
    build_payment_keyboard,
)
from ui.plans import (
    build_plans_keyboard,
    calculate_plan_saving,
    format_amount,
)
from ui.helpers import edit_screen


router = Router(
    name="plans",
)


@router.callback_query(
    F.data.in_({"plans", "subscription_plans"})
)
async def show_plans(
    callback: CallbackQuery,
) -> None:
    await callback.answer()

    try:
        response = await backend_get(
            "/catalog/plans"
        )
    except httpx.RequestError:
        await edit_screen(
            callback,
            "⚠️ Не удалось загрузить тарифы.",
            main_menu,
        )
        return

    if response.status_code != 200:
        await edit_screen(
            callback,
            "⚠️ Не удалось загрузить тарифы.",
            main_menu,
        )
        return

    plans = response.json()

    monthly_plan = next(
        (
            plan
            for plan in plans
            if plan["code"] == "standard_1m"
        ),
        None,
    )

    lines = [
        "💎 Тарифы Work&PlayVPN",
        "",
        "Выберите удобный срок подписки.",
        "В каждый тариф входит до трёх устройств.",
        "",
    ]

    for plan in plans:
        price = format_amount(
            plan["price_amount"]
        )

        devices = plan["device_limit"]

        if plan["code"] == "trial_1d":
            lines.append(
                "🎁 Пробный доступ — бесплатно\n"
                f"   1 день · до {devices} устройств"
            )
        else:
            saving = calculate_plan_saving(
                plan,
                monthly_plan,
            )
            saving_text = (
                f" · выгода {saving} ₽"
                if saving
                else ""
            )
            lines.append(
                f"• {plan['name']} — {price} ₽"
                f"{saving_text}"
            )

    lines.extend(
        [
            "",
            "Дополнительное устройство — 249 ₽.",
            "",
            "Нажмите на подходящий тариф:",
        ]
    )

    source = (
        "subscription"
        if callback.data == "subscription_plans"
        else "main"
    )

    await edit_screen(
        callback,
        "\n".join(lines),
        build_plans_keyboard(
            plans,
            source=source,
        ),
    )


@router.callback_query(
    F.data.startswith("select_plan:")
)
async def select_plan(
    callback: CallbackQuery,
) -> None:
    await callback.answer()

    if callback.data is None:
        return

    callback_parts = callback.data.split(":")
    plan_code = callback_parts[1]
    source = (
        callback_parts[2]
        if len(callback_parts) > 2
        else "main"
    )

    telegram_id = callback.from_user.id

    if plan_code == "trial_1d":
        payload = {
            "telegram_id": telegram_id,
            "plan_code": plan_code,
        }

        try:
            response = await backend_post(
                "/subscriptions",
                payload,
            )
        except httpx.RequestError:
            await edit_screen(
                callback,
                "⚠️ Не удалось активировать "
                "пробный период.",
                main_menu,
            )
            return

        if response.status_code == 201:
            await edit_screen(
                callback,
                "🎉 Пробный период активирован!\n\n"
                "Срок: 1 день\n\n"
                "Теперь можно подключить устройство.",
                main_menu,
            )
            return

        if response.status_code == 409:
            detail = response.json().get(
                "detail"
            )

            messages = {
                "Trial already used": (
                    "🎁 Пробный период уже был "
                    "использован."
                ),
                "User already has active subscription": (
                    "✅ У вас уже есть активная "
                    "подписка."
                ),
            }

            await edit_screen(
                callback,
                messages.get(
                    detail,
                    "Пробный период сейчас недоступен.",
                ),
                main_menu,
            )
            return

        await edit_screen(
            callback,
            "⚠️ Не удалось активировать "
            "пробный период.",
            main_menu,
        )
        return

    try:
        response = await backend_get(
            "/catalog/plans"
        )
    except httpx.RequestError:
        await edit_screen(
            callback,
            "⚠️ Не удалось загрузить тариф.",
            build_back_to_main_keyboard(),
        )
        return

    if response.status_code != 200:
        await edit_screen(
            callback,
            "⚠️ Не удалось загрузить тариф.",
            build_back_to_main_keyboard(),
        )
        return

    plans = response.json()

    plan = next(
        (
            item
            for item in plans
            if item["code"] == plan_code
        ),
        None,
    )

    if plan is None:
        await edit_screen(
            callback,
            "⚠️ Тариф не найден.",
            build_back_to_main_keyboard(),
        )
        return

    price = format_amount(
        plan["price_amount"]
    )

    await edit_screen(
        callback,
        "💳 Подтверждение тарифа\n\n"
        f"Срок: {plan['name']}\n"
        f"К оплате: {price} ₽\n"
        f"Устройств: до {plan['device_limit']}\n\n"
        "После оплаты подписка активируется "
        "автоматически.",
        build_payment_confirmation_keyboard(
            plan_code,
            source=source,
        ),
    )


@router.callback_query(
    F.data.startswith("pay_plan:")
)
async def pay_plan(
    callback: CallbackQuery,
) -> None:
    await callback.answer()

    if callback.data is None:
        return

    callback_parts = callback.data.split(":")
    plan_code = callback_parts[1]
    source = (
        callback_parts[2]
        if len(callback_parts) > 2
        else "main"
    )

    telegram_id = callback.from_user.id

    idempotency_key = (
        f"tg-{telegram_id}-"
        f"{plan_code}-"
        f"{callback.id}"
    )

    payment_payload = {
        "telegram_id": telegram_id,
        "plan_code": plan_code,
        "idempotency_key": idempotency_key,
    }

    try:
        response = await backend_post(
            "/payments",
            payment_payload,
        )
    except httpx.RequestError:
        await edit_screen(
            callback,
            "⚠️ Платёжный сервис временно "
            "недоступен.\n\n"
            "Попробуйте немного позже.",
            build_back_to_main_keyboard(),
        )
        return

    if response.status_code == 201:
        payment = response.json()

        confirmation_url = payment.get(
            "confirmation_url"
        )

        if not confirmation_url:
            await edit_screen(
                callback,
                "⚠️ Не удалось получить "
                "ссылку на оплату.\n\n"
                "Попробуйте ещё раз позже.",
                build_back_to_main_keyboard(),
            )
            return

        amount = format_amount(
            payment["amount"]
        )

        await edit_screen(
            callback,
            "🔐 Безопасная оплата\n\n"
            f"Сумма: {amount} ₽\n\n"
            "Оплата откроется на защищённой "
            "странице платёжного сервиса.\n\n"
            "После успешной оплаты подписка "
            "активируется автоматически.",
            build_payment_keyboard(
                confirmation_url,
                payment["id"],
                source=source,
            ),
        )
        return

    if response.status_code == 409:
        detail = response.json().get(
            "detail"
        )

        messages = {
            "User already has active subscription": (
                "✅ У вас уже есть активная "
                "подписка."
            ),
        }

        await edit_screen(
            callback,
            messages.get(
                detail,
                "Этот платёж сейчас невозможно "
                "создать.",
            ),
            build_back_to_main_keyboard(),
        )
        return

    if response.status_code == 404:
        await edit_screen(
            callback,
            "⚠️ Пользователь или тариф "
            "не найден.\n\n"
            "Попробуйте отправить /start.",
            main_menu,
        )
        return

    if response.status_code == 502:
        await edit_screen(
            callback,
            "⚠️ Платёжная система временно "
            "недоступна.\n\n"
            "Деньги не списаны. "
            "Попробуйте немного позже.",
            build_back_to_main_keyboard(),
        )
        return

    await edit_screen(
        callback,
        "⚠️ Не удалось создать платёж.\n\n"
        "Попробуйте немного позже.",
        build_back_to_main_keyboard(),
    )

@router.callback_query(
    F.data.startswith("cancel_payment:")
)
async def cancel_payment(
    callback: CallbackQuery,
) -> None:
    await callback.answer()

    try:
        payment_id = int(
            callback.data.split(":", 1)[1]
        )
    except (ValueError, IndexError):
        await edit_screen(
            callback,
            "⚠️ Не удалось определить платёж.",
            build_back_to_main_keyboard(),
        )
        return

    try:
        response = await backend_post(
            f"/payments/{payment_id}/cancel",
            {
                "telegram_id": callback.from_user.id,
            },
        )
    except httpx.RequestError:
        await edit_screen(
            callback,
            "⚠️ Не удалось отменить платёж.\n\n"
            "Попробуйте немного позже.",
            build_back_to_main_keyboard(),
        )
        return

    if response.status_code == 200:
        try:
            plans_response = await backend_get(
                "/catalog/plans"
            )
        except httpx.RequestError:
            await edit_screen(
                callback,
                "✅ Платёж отменён.",
                build_back_to_main_keyboard(),
            )
            return

        if plans_response.status_code != 200:
            await edit_screen(
                callback,
                "✅ Платёж отменён.",
                build_back_to_main_keyboard(),
            )
            return

        plans = plans_response.json()

        await edit_screen(
            callback,
            "✅ Платёж отменён.\n\n"
            "Теперь вы можете выбрать другой тариф.",
            build_plans_keyboard(plans),
        )
        return

    if response.status_code == 404:
        await edit_screen(
            callback,
            "⚠️ Платёж не найден.",
            build_back_to_main_keyboard(),
        )
        return

    if response.status_code == 409:
        await edit_screen(
            callback,
            "⚠️ Этот платёж уже нельзя отменить.",
            build_back_to_main_keyboard(),
        )
        return

    await edit_screen(
        callback,
        "⚠️ Не удалось отменить платёж.\n\n"
        "Попробуйте немного позже.",
        build_back_to_main_keyboard(),
    )
