# permissions.py

from functools import wraps
import streamlit as st


def is_admin_user(user: dict | None) -> bool:
    if not user:
        return False
    return str(user.get("role", "")).strip().lower() == "admin"


def require_admin(user: dict | None):
    return is_admin_user(user)


def admin_only_message():
    st.error("Usuário não tem permissão para acessar esta ação.")
    st.stop()


def require_admin_page():
    user = st.session_state.get("user_v5")
    if not is_admin_user(user):
        st.warning("Somente administradores podem acessar esta página.")
        st.stop()
    return user


def admin_only_action(user: dict | None):
    if not is_admin_user(user):
        st.error("Somente administradores podem criar, editar ou cancelar transactions.")
        return False
    return True


def guard_admin_action(user: dict | None):
    def decorator(fn):
        @wraps(fn)
        def wrapper(*args, **kwargs):
            if not is_admin_user(user):
                admin_only_message()
            return fn(*args, **kwargs)
        return wrapper
    return decorator