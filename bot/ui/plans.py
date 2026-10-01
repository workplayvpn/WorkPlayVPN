from aiogram.types import (
    InlineKeyboardButton,
    InlineKeyboardMarkup,
)

from ui.common import build_keyboard


def format_amount(value: object) -> str:
    return str(value).removesuffix(".00")


def calculate_plan_saving(
    plan: dict,
    monthly_plan: dict | None,
) -> int:
    if monthly_plan is None:
        return 0

    months = round(plan["duration_days"] / 30)

    if months <= 1:
        return 0

    monthly_price = float(
        monthly_plan["price_amount"]
    )
    plan_price = float(plan["price_amount"])

    return max(
        0,
        round(monthly_price * months - plan_price),
    )


def build_plans_keyboard(
    plans: list[dict],
    *,
    source: str = "main",
) -> InlineKeyboardMarkup:
    rows = []
    monthly_plan = next(
        (
            plan
            for plan in plans
            if plan["duration_days"] == 30
        ),
        None,
    )

    for plan in plans:
        if plan["code"] == "trial_1d":
            text = "🎁 Попробовать бесплатно — 1 день"
        else:
            price = format_amount(
                plan["price_amount"]
            )
            saving = calculate_plan_saving(
                plan,
                monthly_plan,
            )

            suffix = (
                f" · выгода {saving} ₽"
                if saving
                else ""
            )
            text = (
                f"{plan['name']} — {price} ₽"
                f"{suffix}"
            )

        rows.append(
            [
                InlineKeyboardButton(
                    text=text,
                    callback_data=(
                        f"select_plan:{plan['code']}:{source}"
                    ),
                )
            ]
        )

    rows.append(
        [
            InlineKeyboardButton(
                text=(
                    "← Назад"
                    if source == "subscription"
                    else "← На главную"
                ),
                callback_data=(
                    "subscription"
                    if source == "subscription"
                    else "main_menu"
                ),
            )
        ]
    )

    return build_keyboard(
        inline_keyboard=rows,
    )
