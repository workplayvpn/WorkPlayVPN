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
    tier = "mobile" if any(p.get("access_tier") == "mobile" for p in plans) else "basic"
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
            days = plan["duration_days"]
            duration = "7 дней" if days == 7 else "1 месяц" if days == 30 else f"{round(days / 30)} месяца" if days == 90 else f"{round(days / 30)} месяцев"
            text = f"{duration} — {price} ₽{suffix}"

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

    back = f"subscription_tier:{source[6:]}" if source in ("renew_basic", "renew_mobile") else "plans"
    rows.append([InlineKeyboardButton(text="← Назад", callback_data=back)])

    return build_keyboard(
        inline_keyboard=rows,
    )
