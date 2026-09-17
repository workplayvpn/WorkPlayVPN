from aiogram import F, Router
from aiogram.types import CallbackQuery

from ui.common import build_back_to_main_keyboard
from ui.helpers import edit_screen


router = Router(
    name="help",
)


@router.callback_query(
    F.data.in_({"help", "report_problem"})
)
async def show_help(
    callback: CallbackQuery,
) -> None:
    await callback.answer()

    if callback.data == "report_problem":
        text = (
            "🛟 Сообщить о проблеме\n\n"
            "Опишите, что произошло, и укажите:\n\n"
            "• модель устройства;\n"
            "• операционную систему;\n"
            "• тип сети — Wi-Fi или мобильная;\n"
            "• на каком шаге появилась ошибка.\n\n"
            "Поддержка: support@workplayvpn.ru\n\n"
            "Не отправляйте ключ подписки, пароль "
            "или платёжные данные."
        )
    else:
        text = (
        "🛟 Как подключиться\n\n"
        "1. Откройте приложение Work&PlayVPN.\n"
        "2. Выберите и оплатите тариф.\n"
        "3. Нажмите «Подключить устройство».\n"
        "4. Выберите доступный сервер.\n"
        "5. Следуйте инструкции по установке HAPP.\n\n"
        "Ссылка подключения создаётся отдельно "
        "для каждого устройства. Не передавайте "
        "её другим людям.\n\n"
        "Если данные не обновились, вернитесь "
        "на главную и откройте раздел ещё раз.\n\n"
        "Поддержка: support@workplayvpn.ru"
        )

    await edit_screen(
        callback,
        text,
        build_back_to_main_keyboard(),
    )
