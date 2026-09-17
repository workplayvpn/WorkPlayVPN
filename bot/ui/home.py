def build_home_text(
    first_name: str,
    *,
    is_new_user: bool = False,
) -> str:
    if is_new_user:
        greeting = f"Добро пожаловать, {first_name}!"
    else:
        greeting = f"Рады видеть вас, {first_name}!"

    return (
        f"👋 {greeting}\n\n"
        "Work&PlayVPN — защищённое подключение "
        "для работы, общения и развлечений.\n\n"
        "⚡ Быстрое подключение\n"
        "📱 До трёх устройств\n"
        "🌍 Выбор доступного сервера\n"
        "🔐 Управление ключом и подключениями\n\n"
        "Откройте приложение или выберите нужный раздел:"
    )
