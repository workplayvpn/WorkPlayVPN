from aiogram.types import (
    InlineKeyboardButton,
    InlineKeyboardMarkup,
)


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
) -> InlineKeyboardMarkup:
    rows = []
    monthly_plan = next(
        (
            plan
            for plan in plans
            if plan["code"] == "standard_1m"
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
                        f"select_plan:{plan['code']}"
                    ),
                )
            ]
        )

    rows.append(
        [
            InlineKeyboardButton(
                text="← На главную",
                callback_data="main_menu",
            )
        ]
    )

    return InlineKeyboardMarkup(
        inline_keyboard=rows,
    )
