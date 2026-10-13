import pandas as pd
import streamlit as st
import time
from app_lib.season_config import (
    ACTIVE_SEASON,
    SEASONS,
    SEASON_LABELS,
)
from app_lib.fantasy_data_service import load_fantasy_data_from_neon
from app_lib.role_helpers import is_admin_user
from app_lib.session_helpers import require_login_v5
from app_lib.team_tabs_ui import (
    render_main_tab,
    render_dev_tab,
    render_picks_tab,
)

from app_lib.teams_page_context import build_teams_page_context
from app_lib.teams_ui_helpers import (
    currency,
    inject_summary_card_css,
    render_summary_card,
)
from app_lib.transactions_ui import render_transactions_tab
from app_lib.transforms import get_team_options


@st.cache_data(
    ttl=900,
    show_spinner=False,
)
def cached_load():
    """
    Carrega a base de Elencos a partir do Neon.

    O retorno mantém o mesmo contrato usado anteriormente:
    data["teams"], data["players"], data["roster"], data["development"],
    data["fines"], data["picks"], data["transactions"] e
    data["transactionitems"].
    """
    return load_fantasy_data_from_neon()


def load_current_data():
    """
    Mantém a função de carregamento isolada para preservar o fluxo
    atual da página, alterando somente a origem dos dados: Excel -> Neon.
    """
    return cached_load()


user = require_login_v5()
is_admin = is_admin_user(user)


# Cabeçalho clean
st.title("Elencos")
st.caption("Visão geral do time e movimentações")


start_load = time.perf_counter()

data = load_current_data()

load_seconds = time.perf_counter() - start_load

#st.caption(
#    f"⏱️ Carregamento Neon: {load_seconds:.2f}s"
#)

if data is None:
    st.error("Não foi possível carregar os dados de Elencos no Neon.")
    st.stop()

teams = get_team_options(data["teams"])

if teams.empty:
    st.error("Nenhum time encontrado nos dados carregados do Neon.")
    st.stop()


if "teams_selected_team_name_v1" not in st.session_state:
    st.session_state.teams_selected_team_name_v1 = (
        teams["team_name"].tolist()[0]
    )


if "teams_selected_start_season_v1" not in st.session_state:
    st.session_state.teams_selected_start_season_v1 = (
        ACTIVE_SEASON
        if ACTIVE_SEASON in SEASONS
        else SEASONS[0]
    )

season_key_by_label = {
    str(label): key
    for key, label in SEASON_LABELS.items()
}

stored_season = st.session_state.get(
    "teams_selected_start_season_v1"
)

if stored_season in season_key_by_label:
    st.session_state.teams_selected_start_season_v1 = (
        season_key_by_label[stored_season]
    )

if (
    st.session_state.get(
        "teams_selected_start_season_v1"
    )
    not in SEASONS
):
    st.session_state.teams_selected_start_season_v1 = (
        ACTIVE_SEASON
        if ACTIVE_SEASON in SEASONS
        else SEASONS[0]
    )

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


start_context = time.perf_counter()

ctx = build_teams_page_context(
    data=data,
    selected_team_name=selected_team_name,
    selected_start_season=selected_start_season,
    workbook_path=None,
)

context_seconds = time.perf_counter() - start_context

#st.caption(
#    f"⏱️ Contexto Elencos: {context_seconds:.2f}s"
#)


selected_team_id = ctx["selected_team_id"]
main_roster = ctx["main_roster"]
dev_roster = ctx["dev_roster"]
main_summary = ctx["main_summary"]
total_picks = ctx["total_picks"]
cap_remaining = ctx["cap_remaining"]
cap_status = ctx["cap_status"]


inject_summary_card_css()


# Cards de resumo (mantidos + novo card "Disponível")
row1 = st.columns(3)

with row1[0]:
    render_summary_card("Time", selected_team_name)

with row1[1]:
    render_summary_card("Jogadores MAIN", len(main_roster))

with row1[2]:
    render_summary_card("Jogadores DEV", len(dev_roster))


salarios_main = main_summary.get(
    "Salários",
    0.0,
)

disponivel = main_summary.get(
    "Disponível",
    0.0,
)


row2 = st.columns(4)

with row2[0]:
    render_summary_card("Salários MAIN", currency(salarios_main))

with row2[1]:
    render_summary_card("Cap restante", currency(cap_remaining))

with row2[2]:
    render_summary_card("Picks", total_picks)

with row2[3]:
    render_summary_card("Disponível", currency(disponivel))


st.caption(f"Status do cap: {cap_status}")
st.divider()


# Busca global de jogadores (MAIN + DEV) com selectbox pesquisável
st.subheader("Buscar jogador")


# Junta roster/dev com players para trazer player_name
roster_df = data[
    "roster"
].copy().assign(
    Elenco="MAIN"
)

dev_df = data[
    "development"
].copy().assign(
    Elenco="DEV"
)

players_df = data.get(
    "players",
    pd.DataFrame(),
)

all_players = pd.concat(
    [
        roster_df,
        dev_df,
    ],
    ignore_index=True,
)

all_players = all_players.drop_duplicates(
    subset=[
        column
        for column in [
            "team_id",
            "player_id",
            "Elenco",
        ]
        if column in all_players.columns
    ],
    keep="first",
)

if (
    not players_df.empty
    and "player_id" in all_players.columns
    and "player_id" in players_df.columns
):
    all_players = all_players.merge(
        players_df[["player_id", "player_name"]],
        on="player_id",
        how="left",
    )
else:
    st.warning(
        "Base de jogadores não encontrada ou sem colunas necessárias."
    )
    all_players["player_name"] = all_players["player_id"].astype(str)


player_options = sorted(
    all_players["player_name"].dropna().unique().tolist()
)

selected_player = st.selectbox(
    "Jogador",
    options=[""] + player_options,
    index=0,
    key="player_search_select",
)


if selected_player:
    found = all_players.loc[
        all_players["player_name"] == selected_player
    ].copy()

    if not found.empty:
        show = found[
            ["player_name", "team_id", "Elenco"]
        ].copy()

        team_lookup = ctx["team_lookup"]

        show["Time"] = (
            show["team_id"]
            .map(team_lookup)
            .fillna(show["team_id"])
        )

        show = show.rename(
            columns={
                "player_name": "Jogador",
                "team_id": "ID Time",
                "Elenco": "Elenco",
                "Time": "Time",
            }
        )

        st.dataframe(
            show[["Jogador", "Time", "Elenco"]],
            use_container_width=True,
            hide_index=True,
        )
else:
    st.caption(
        "Selecione ou digite o nome do jogador para buscar em todos "
        "os elencos (MAIN e DEV)."
    )


st.divider()


# Abas clean
tab_main, tab_dev, tab_picks, tab_transactions = st.tabs(
    [
        "Principal",
        "Desenvolvimento",
        "Picks",
        "Transações",
    ]
)


with tab_main:
    render_main_tab(ctx)


with tab_dev:
    render_dev_tab(ctx)


with tab_picks:
    render_picks_tab(ctx)


with tab_transactions:
    start_transactions = time.perf_counter()

    render_transactions_tab(
        data=data,
        teams=data["teams"],
        selected_team_id=selected_team_id,
        team_transactions_df=ctx["team_transactions_df"],
        team_lookup=ctx["team_lookup"],
        player_lookup=ctx["player_lookup"],
        user=user,
        is_admin=is_admin,
        DEFAULT_FILE=None,
    )

    transactions_seconds = (
        time.perf_counter()
        - start_transactions
    )

    st.caption(
        "⏱️ Transações: "
        f"{transactions_seconds:.2f}s"
    )