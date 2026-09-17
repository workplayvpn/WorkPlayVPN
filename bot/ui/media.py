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
