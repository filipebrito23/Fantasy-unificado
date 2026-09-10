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
st.caption("Painel principal da liga")

ctx = build_home_page_context(user=user, user_label=user_label, is_admin=is_admin)

if ctx.tabs_df.empty:
    st.info("Nenhuma aba ativa cadastrada.")
    st.stop()

# Cabeçalho executivo
header_cols = st.columns([2.2, 1.2, 1.2])
with header_cols[0]:
    st.markdown(f"### Bem-vindo, {user_label}")
    st.caption("Aqui você encontra a visão geral da liga, atalhos úteis e recados importantes.")
with header_cols[1]:
    st.metric("Aba ativa", len(ctx.tabs_df))
with header_cols[2]:
    st.metric("Perfil", "Admin" if is_admin else "Usuário")

st.divider()


render_home_tabs(ctx)
