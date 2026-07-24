import streamlit as st

from app_lib.db_v5 import init_db_v5, healthcheck_db_v5, is_postgres_v5
from app_lib.auction_v5 import close_expired_bids_v5
from app_lib.auth_ui import render_login_v5, render_force_password_change_v5
from app_lib.role_helpers import get_user_display
from app_lib.session_helpers import (
    init_session_v5,
    get_current_user_v5,
    logout_v5,
)

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


ok_startup, startup_error = startup_v5()
if not ok_startup:
    st.error(f"Erro ao inicializar aplicação: {startup_error}")
    st.stop()

init_session_v5()

st.sidebar.caption(f"Ambiente: {get_environment_label_v5()}")
st.sidebar.caption("Banco: PostgreSQL" if is_postgres_v5() else "Banco: SQLite")

user = get_current_user_v5()
if not user:
    render_login_v5()

user = get_current_user_v5()

st.sidebar.success(f"Logado como {get_user_display(user)} ({user['role']})")
if user.get("team_name"):
    st.sidebar.write(f"Time vinculado: {user['team_name']}")

if st.sidebar.button("Sair"):
    logout_v5()

if user.get("must_change_password") == 1:
    render_force_password_change_v5(user)

pg = st.navigation(
    [
        st.Page("pages/home.py", title="Home"),
        st.Page("pages/teams.py", title="Elencos"),
        st.Page("pages/lei.py", title="Leilão"),
        st.Page("pages/classificacao.py", title="Classificação"),
    ]
)

pg.run()