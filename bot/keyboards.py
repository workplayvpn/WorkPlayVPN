from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup


main_menu = InlineKeyboardMarkup(
    inline_keyboard=[
        [
            InlineKeyboardButton(
                text="💳 Тарифы",
                callback_data="plans",
            ),
            InlineKeyboardButton(
                text="👤 Мой профиль",
                callback_data="profile",
            ),
        ],
        [
            InlineKeyboardButton(
                text="🌍 Страны",
                callback_data="locations",
            ),
            InlineKeyboardButton(
                text="❓ Помощь",
                callback_data="help",
            ),
        ],
    ]
)


def build_plans_keyboard(
    plans: list[dict],
) -> InlineKeyboardMarkup:
    rows = []

    for plan in plans:
        if plan["code"] == "trial_3d":
            text = "🎁 Пробный — 3 дня бесплатно"
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