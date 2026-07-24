from __future__ import annotations

import pandas as pd
import streamlit as st

from app_lib.auction_formatters import formatar_brl, format_remaining, valor_por_extenso
from app_lib.auction_service import (
    get_all_bids_v5,
    get_audit_rows_v5,
    get_bid_history_v5,
    get_players_with_state_v5,
    get_team_rows_v5,
)


def is_admin_user(user):
    if isinstance(user, dict):
        return str(user.get("role", "")).lower() == "admin"
    return False


def render_auction_players_tab(position_filter: str, status_filter: str):
    players = get_players_with_state_v5(position_filter)
    df = pd.DataFrame(players)
    if df.empty:
        st.info("Nenhum jogador encontrado.")
        return
    if status_filter != "Todos" and "status" in df.columns:
        df = df[df["status"].fillna("-").astype(str).str.upper() == status_filter.upper()]
    st.dataframe(df, use_container_width=True, hide_index=True)


def render_auction_bid_form_tab(user, team_id, selected_player_id=None, selected_player_name=None):
    st.subheader("Nova proposta")
    if selected_player_name:
        st.info(f"Jogador selecionado: {selected_player_name}")
        history = pd.DataFrame(get_bid_history_v5(selected_player_id)) if selected_player_id else pd.DataFrame()
        if not history.empty:
            active = history[history["is_active"] == 1].head(1)
            if not active.empty:
                row = active.iloc[0]
                st.caption(f"Proposta ativa atual: {formatar_brl(row['amount'])} em {int(row['years'])} anos")
                st.caption(f"Tempo restante: {format_remaining(row.get('created_at'))}")
    with st.form("auction_bid_form", clear_on_submit=True):
        player_id = st.number_input("Player ID", min_value=1, step=1, value=int(selected_player_id or 1))
        amount = st.number_input("Valor", min_value=0.0, step=0.5, format="%.2f")
        years = st.number_input("Anos", min_value=1, step=1, value=1)
        submitted = st.form_submit_button("Enviar proposta")
        if submitted:
            st.success("Formulário pronto para integrar com submit_bid_v5.")


def render_auction_cap_tab():
    st.subheader("Cap")
    teams = pd.DataFrame(get_team_rows_v5())
    if teams.empty:
        st.info("Sem dados de cap.")
        return
    show = teams[[c for c in ["team_name", "cap_limit", "used_cap", "available_cap"] if c in teams.columns]].copy()
    show = show.rename(columns={"team_name": "Time", "cap_limit": "Cap", "used_cap": "Usado", "available_cap": "Disponível"})
    st.metric("Times", len(show))
    st.dataframe(show.sort_values("Disponível", ascending=False), use_container_width=True, hide_index=True)


def render_auction_admin_tab():
    st.subheader("Admin")
    tabs = st.tabs(["Propostas", "Usuários", "Auditoria"])
    with tabs[0]:
        st.dataframe(pd.DataFrame(get_all_bids_v5()), use_container_width=True, hide_index=True)
    with tabs[1]:
        st.info("Conecte aqui a listagem de usuários existente no sistema.")
    with tabs[2]:
        st.dataframe(pd.DataFrame(get_audit_rows_v5()), use_container_width=True, hide_index=True)


def render_auction_profile_tab(user):
    st.subheader("Perfil")
    st.write(user)
