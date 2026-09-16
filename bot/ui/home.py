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
        "🛡 Work&PlayVPN\n"
        "Защищённый интернет без сложных настроек\n\n"
        f"{greeting}\n\n"
        "• подключение через удобное приложение\n"
        "• до трёх устройств в одном тарифе\n"
        "• автоматическая активация после оплаты\n\n"
        "Откройте приложение или выберите раздел:"
    )
