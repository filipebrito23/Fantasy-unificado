import streamlit as st

from db_v5 import init_db_v5, healthcheck_db_v5, is_postgres_v5
from auth_v5 import authenticate_user_v5, change_password_v5
from auction_v5 import close_expired_bids_v5


st.set_page_config(page_title="Fantasy NBA System", layout="wide")


def get_environment_label_v5():
    app_cfg = st.secrets.get("app", {})
    return str(app_cfg.get("environment", "development")).lower()


def startup_v5():
    try:
        healthcheck_db_v5()
        init_db_v5()
        close_expired_bids_v5()
        return True, None
    except Exception as e:
        return False, str(e)


def init_session_v5():
    if "user_v5" not in st.session_state:
        st.session_state.user_v5 = None


def logout_v5():
    st.session_state.user_v5 = None
    st.rerun()


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
                st.session_state.user_v5 = user
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
                st.session_state.user_v5["must_change_password"] = 0
                st.success("Senha alterada com sucesso.")
                st.rerun()

    st.stop()


ok_startup, startup_error = startup_v5()
if not ok_startup:
    st.error(f"Erro ao inicializar aplicação: {startup_error}")
    st.stop()

init_session_v5()

st.sidebar.caption(f"Ambiente: {get_environment_label_v5()}")
st.sidebar.caption("Banco: PostgreSQL" if is_postgres_v5() else "Banco: SQLite")

if not st.session_state.user_v5:
    render_login_v5()

user = st.session_state.user_v5

st.sidebar.success(f"Logado como {user['email']} ({user['role']})")
if user.get("team_name"):
    st.sidebar.write(f"Time vinculado: {user['team_name']}")

if st.sidebar.button("Sair"):
    logout_v5()

if user.get("must_change_password") == 1:
    render_force_password_change_v5(user)

pg = st.navigation(
    [
        st.Page("pages/lei.py", title="Leilão"),
        st.Page("pages/teams.py", title="Elencos"),
        st.Page("pages/classificacao.py", title="Classificação"),
    ]
)

pg.run()