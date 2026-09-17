from aiogram import F, Router
from aiogram.types import CallbackQuery

from ui.documents import (
    build_document_back_keyboard,
    build_documents_keyboard,
)
from ui.helpers import edit_screen


router = Router(name="documents")


@router.callback_query(F.data == "documents")
async def show_documents(callback: CallbackQuery) -> None:
    await callback.answer()

    await edit_screen(
        callback,
        "📄 Документы Work&PlayVPN\n\n"
        "Здесь собраны условия использования сервиса, "
        "правила обработки данных и возврата средств.\n\n"
        "Выберите документ:",
        build_documents_keyboard(),
    )


@router.callback_query(F.data.startswith("document:"))
async def show_document(callback: CallbackQuery) -> None:
    await callback.answer()

    document_code = (callback.data or "").split(":", 1)[-1]

    documents = {
        "offer": (
            "📃 Публичная оферта\n\n"
            "Документ определяет порядок предоставления доступа, "
            "оплаты, активации и использования Work&PlayVPN.\n\n"
            "Полная юридическая редакция готовится к публикации "
            "на сайте до коммерческого запуска сервиса."
        ),
        "privacy": (
            "🔐 Политика конфиденциальности\n\n"
            "Work&PlayVPN использует Telegram ID, имя профиля "
            "и технические данные, необходимые для работы "
            "подписки и подключённых устройств.\n\n"
            "Платёжные реквизиты обрабатываются платёжным "
            "провайдером и не сохраняются ботом."
        ),
        "refund": (
            "↩️ Условия возврата\n\n"
            "Для обращения по возврату напишите на "
            "support@workplayvpn.ru и укажите Telegram ID, "
            "дату и сумму оплаты.\n\n"
            "Каждое обращение рассматривается с учётом причины, "
            "срока использования и применимых требований закона."
        ),
        "details": (
            "🏢 Реквизиты сервиса\n\n"
            "Исполнитель: самозанятый\n"
            "Проект: Work&PlayVPN\n"
            "Сайт: workplayvpn.ru\n"
            "Поддержка: support@workplayvpn.ru\n\n"
            "Полные реквизиты будут опубликованы в оферте."
        ),
    }

    await edit_screen(
        callback,
        documents.get(
            document_code,
            "Документ не найден.",
        ),
        build_document_back_keyboard(),
    )
