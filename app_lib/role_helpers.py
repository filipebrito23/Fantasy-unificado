def is_admin_user(user: dict | None) -> bool:
    if not isinstance(user, dict):
        return False
    return str(user.get("role", "")).strip().lower() == "admin"


def get_user_display(user) -> str:
    if isinstance(user, dict):
        return str(
            user.get("name")
            or user.get("username")
            or user.get("email")
            or "Usuário"
        )
    return str(user or "Usuário")