import streamlit as st

SESSION_USER_KEY = "user_v5"


def init_session_v5():
    if SESSION_USER_KEY not in st.session_state:
        st.session_state[SESSION_USER_KEY] = None


def get_current_user_v5():
    return st.session_state.get(SESSION_USER_KEY)


def set_current_user_v5(user: dict | None):
    st.session_state[SESSION_USER_KEY] = user


def require_login_v5():
    user = get_current_user_v5()
    if not user:
        st.warning("Faça login para acessar esta página.")
        st.stop()
    return user


def logout_v5():
    set_current_user_v5(None)
    st.rerun()