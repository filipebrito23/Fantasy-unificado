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

# Blocos principais
block_cols = st.columns([1.2, 1.2, 1.2])
with block_cols[0]:
    st.subheader("Resumo da liga")
    st.write("Liga Fantasy no formato keeper iniciada em 2021-22.")
    st.write("Galeria dos campeões:")
    st.write("• Itajubá Rabbits (2021-22, 2025-26)")
    st.write("• Alabama Black Bears (2022-23)")
    st.write("• Las Vegas Breakers (2023-24)")
    st.write("• Miami Barons (2024-25)")

with block_cols[1]:
    st.subheader("Atalhos")
    shortcut_cols = st.columns(3)
    with shortcut_cols[0]:
        st.page_link("pages/teams.py", label="Elencos")
    with shortcut_cols[1]:
        st.page_link("pages/lei.py", label="Leilão")
    with shortcut_cols[2]:
        st.page_link("pages/classificacao.py", label="Classificação")

with block_cols[2]:
    st.subheader("Avisos")
    st.write("• Início da FA em 14/07/2026 às 12h00")
    st.write("• Durante a temporada regular, não esqueca de escalar seu time.")

st.divider()

render_home_tabs(ctx)
