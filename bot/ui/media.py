from aiogram.types import FSInputFile, Message


WELCOME_PHOTO_PATH = "assets/welcome.png"

_welcome_photo_file_id: str | None = None


def get_welcome_photo() -> str | FSInputFile:
    return (
        _welcome_photo_file_id
        or FSInputFile(WELCOME_PHOTO_PATH)
    )


def remember_welcome_photo(message: Message) -> None:
    global _welcome_photo_file_id

    if message.photo:
        _welcome_photo_file_id = message.photo[-1].file_id


def reset_welcome_photo() -> None:
    global _welcome_photo_file_id
    _welcome_photo_file_id = None


def get_screen_photo(callback_data: str | None, text: str) -> FSInputFile:
    data = callback_data or ""
    if data == "main_menu":
        name = "welcome"
    elif text.startswith("⚠️"):
        name = "error"
    elif data.startswith("subscription_key"):
        name = "key"
    elif data.startswith("subscription_tier:"):
        name = "mobile" if data.endswith(":mobile") else "basic"
    elif data.startswith("subscription") and data != "subscription_plans":
        name = "subscription"
    elif data.startswith("plans_tier") or data == "subscription_plans":
        name = "terms"
    elif data == "plans":
        name = "plans"
    elif data.startswith(("select_plan:", "pay_plan:", "cancel_payment:")):
        name = "payment"
    elif data == "profile":
        name = "profile"
    elif "location" in data or data.startswith(("change_region", "account_region:")):
        name = "region"
    elif "device" in data:
        name = "devices"
    elif data == "help":
        name = "help"
    elif "document" in data:
        name = "documents"
    else:
        name = "welcome"
    return FSInputFile(f"assets/screens/{name}.png")
