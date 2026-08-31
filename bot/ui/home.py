def build_home_text(
    first_name: str,
    *,
    is_new_user: bool = False,
) -> str:
    if is_new_user:
        greeting = f"Добро пожаловать, {first_name}!"
    else:
        greeting = f"С возвращением, {first_name}!"

    return (
        "🛡 Work&PlayVPN\n\n"
        f"{greeting}\n\n"
        "Быстрый и безопасный доступ к интернету.\n\n"
        "Выберите нужный раздел:"
    )
