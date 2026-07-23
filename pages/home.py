from __future__ import annotations

import streamlit as st

from app_lib.home_page_context import build_home_page_context
from app_lib.home_tabs_ui import render_home_tabs
from app_lib.permissions import is_admin_user
from app_lib.session_helpers import require_login_v5


user = require_login_v5()
user_label = (
    str(user.get("name") or user.get("username") or user.get("email") or "Usuário")
    if isinstance(user, dict)
    else str(user)
)
is_admin = is_admin_user(user)

st.title("Home")
st.caption("Página principal da liga")

ctx = build_home_page_context(user=user, user_label=user_label, is_admin=is_admin)

if ctx.tabs_df.empty:
    st.info("Nenhuma aba ativa cadastrada.")
    st.stop()

render_home_tabs(ctx)