from aiogram.types import (
    InlineKeyboardButton,
    InlineKeyboardMarkup,
)


def build_plans_keyboard(
    plans: list[dict],
) -> InlineKeyboardMarkup:
    rows = []

    for plan in plans:
        if plan["code"] == "trial_1d":
            text = "🎁 Пробный — бесплатно"
        else:
            price = str(
                plan["price_amount"]
            ).removesuffix(".00")

            text = f"{plan['name']} — {price} ₽"

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
                text="⬅️ Главное меню",
                callback_data="main_menu",
            )
        ]
    )

    return InlineKeyboardMarkup(
        inline_keyboard=rows,
    )