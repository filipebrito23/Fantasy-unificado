from pathlib import Path

import pandas as pd
import streamlit as st

from app_lib.data_loader import load_workbook_data, SEASONS
from app_lib.role_helpers import is_admin_user
from app_lib.session_helpers import require_login_v5
from app_lib.team_tabs_ui import render_main_tab, render_dev_tab, render_picks_tab
from app_lib.teams_page_context import build_teams_page_context
from app_lib.teams_ui_helpers import (
    currency,
    inject_summary_card_css,
    render_summary_card,
)
from app_lib.transactions_ui import render_transactions_tab
from app_lib.transforms import SEASON_LABELS, get_team_options


DEFAULT_FILE = Path("roster.xlsx")


@st.cache_data
def cached_load(file_path: str):
    return load_workbook_data(file_path)


user = require_login_v5()
is_admin = is_admin_user(user)

st.title("Elencos Fantasy NBA")
st.caption("Elencos 2026-27")

if not DEFAULT_FILE.exists():
    st.error("Arquivo roster.xlsx não encontrado na pasta do projeto.")
    st.stop()

data = cached_load(str(DEFAULT_FILE))
teams = get_team_options(data["teams"])

if teams.empty:
    st.error("Nenhum time encontrado nos dados carregados.")
    st.stop()

if "teams_selected_team_name_v1" not in st.session_state:
    st.session_state["teams_selected_team_name_v1"] = teams["team_name"].tolist()[0]

if "teams_selected_start_season_v1" not in st.session_state:
    st.session_state["teams_selected_start_season_v1"] = SEASONS[0]

c1, c2 = st.columns([2, 1])

with c1:
    selected_team_name = st.selectbox(
        "Selecione o time",
        teams["team_name"].tolist(),
        key="teams_selected_team_name_v1",
    )

with c2:
    selected_start_season = st.selectbox(
        "Temporada inicial",
        SEASONS,
        format_func=lambda x: SEASON_LABELS[x],
        key="teams_selected_start_season_v1",
    )

ctx = build_teams_page_context(
    data=data,
    selected_team_name=selected_team_name,
    selected_start_season=selected_start_season,
)

selected_team_id = ctx["selected_team_id"]
main_roster = ctx["main_roster"]
dev_roster = ctx["dev_roster"]
main_summary = ctx["main_summary"]
total_picks = ctx["total_picks"]
cap_remaining = ctx["cap_remaining"]
cap_status = ctx["cap_status"]

inject_summary_card_css()

row_1 = st.columns(3)
with row_1[0]:
    render_summary_card("Time", selected_team_name)
with row_1[1]:
    render_summary_card("MAIN players", len(main_roster))
with row_1[2]:
    render_summary_card("DEV players", len(dev_roster))

row_2 = st.columns(3)
with row_2[0]:
    render_summary_card("Salários MAIN", currency(main_summary.get("Salários", 0.0)))
with row_2[1]:
    render_summary_card("Cap restante", currency(cap_remaining))
with row_2[2]:
    render_summary_card("Picks", total_picks)

st.markdown(f"**Status do cap:** {cap_status}")
st.divider()

tab_main, tab_dev, tab_picks, tab_transactions = st.tabs(
    ["Principal", "Development", "Picks", "Transactions"]
)

with tab_main:
    render_main_tab(ctx)

with tab_dev:
    render_dev_tab(ctx)

with tab_picks:
    render_picks_tab(ctx)

with tab_transactions:
    render_transactions_tab(
        data=data,
        teams=teams,
        selected_team_id=selected_team_id,
        team_transactions_df=ctx["team_transactions_df"],
        team_lookup=ctx["team_lookup"],
        player_lookup=ctx["player_lookup"],
        user=user,
        is_admin=is_admin,
        DEFAULT_FILE=DEFAULT_FILE,
    )