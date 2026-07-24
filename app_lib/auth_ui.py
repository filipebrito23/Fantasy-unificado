import streamlit as st

from app_lib.auth_v5 import authenticate_user_v5, change_password_v5
from app_lib.session_helpers import set_current_user_v5


def render_login_v5():
    st.title("Fantasy NBA System")
    st.subheader("Login por e-mail")

    with st.form("login_form_v5"):
        email = st.text_input("E-mail")
        password = st.text_input("Senha", type="password")
        submitted = st.form_submit_button("Entrar")

    if submitted:
        user = authenticate_user_v5(email, password)
        if user:
            set_current_user_v5(user)
            st.rerun()
        else:
            st.error("E-mail ou senha inválidos.")

    st.stop()


def render_force_password_change_v5(user):
    st.warning("Você precisa trocar sua senha antes de continuar.")

    with st.form("change_password_first_login_v5"):
        new_password = st.text_input("Nova senha", type="password")
        confirm_password = st.text_input("Confirmar nova senha", type="password")
        submit_change = st.form_submit_button("Salvar nova senha")

    if submit_change:
        if not new_password or len(new_password) < 6:
            st.error("A senha deve ter pelo menos 6 caracteres.")
        elif new_password != confirm_password:
            st.error("As senhas não coincidem.")
        else:
            change_password_v5(user["user_id"], new_password)
            user["must_change_password"] = 0
            set_current_user_v5(user)
            st.success("Senha alterada com sucesso.")
            st.rerun()

    st.stop()