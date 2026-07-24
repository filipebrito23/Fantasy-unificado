from __future__ import annotations

from pathlib import Path

import pandas as pd
import streamlit as st

from app_lib.data_loader import load_workbook_data
from app_lib.standings_service import build_classification_bundle

DEFAULT_FILE = Path("roster.xlsx")
PLAYOFF_SPOTS = 8
ELIMINATED_SPOTS = 6


@st.cache_data
def cached_load(file_path: str):
    return load_workbook_data(file_path)


def add_status(df: pd.DataFrame) -> pd.DataFrame:
    out = df.copy()
    out["Status"] = "Neutro"
    n = len(out)
    if n > 0:
        out.loc[out.index < min(PLAYOFF_SPOTS, n), "Status"] = "Playoff"
        out.loc[out.index >= max(n - ELIMINATED_SPOTS, 0), "Status"] = "Eliminado"
    return out


def style_table(df: pd.DataFrame):
    def _row_style(row):
        status = row.get("Status", "Neutro")
        if status == "Playoff":
            return ["background-color: #1f5a31; color: #f7fff8; font-weight: 600;"] * len(row)
        if status == "Eliminado":
            return ["background-color: #6b1f2a; color: #fff5f6; font-weight: 600;"] * len(row)
        return ["background-color: #2a2d33; color: #f0f3f8;"] * len(row)
    return df.style.apply(_row_style, axis=1)


def render_classificacao_principal(standings_df: pd.DataFrame):
    st.subheader("Classificação")
    st.caption(f"Top {PLAYOFF_SPOTS} avançam para os playoffs. Os últimos {ELIMINATED_SPOTS} são eliminados.")
    styled = add_status(standings_df)
    st.table(style_table(styled))


def render_playoffs_eliminados(standings_df: pd.DataFrame):
    top = standings_df.head(PLAYOFF_SPOTS)[["Posição", "Time", "Vitórias", "Derrotas", "Saldo"]] if not standings_df.empty else pd.DataFrame()
    bottom = standings_df.tail(ELIMINATED_SPOTS)[["Posição", "Time", "Vitórias", "Derrotas", "Saldo"]] if not standings_df.empty else pd.DataFrame()
    c1, c2 = st.columns(2)
    with c1:
        st.markdown("### Playoffs")
        if top.empty:
            st.info("Sem dados.")
        else:
            st.table(top)
    with c2:
        st.markdown("### Eliminados")
        if bottom.empty:
            st.info("Sem dados.")
        else:
            st.table(bottom)


def render_confronto_tab(matrix_df: pd.DataFrame):
    st.subheader("Confronto direto")
    st.caption("A matriz mostra o retrospecto entre todos os times.")
    st.table(matrix_df)


def render_calendario_tab(schedule_check_df: pd.DataFrame, games_df: pd.DataFrame):
    st.subheader("Calendário")
    st.caption("Resumo de validação do calendário e confrontos realizados.")
    if schedule_check_df.empty:
        st.info("Sem jogos para validar.")
    else:
        st.table(schedule_check_df)
    with st.expander("Jogos da base", expanded=False):
        cols = [c for c in games_df.columns if c not in {"id_jogo", "id_time_1", "id_time_2"}]
        st.table(games_df[cols] if cols else games_df)


def main():
    st.title("Classificação")
    st.caption("Classificação, confronto direto e calendário da temporada")

    if not DEFAULT_FILE.exists():
        st.error("Arquivo roster.xlsx não encontrado na pasta do projeto.")
        st.stop()

    data = cached_load(str(DEFAULT_FILE))
    if "games" not in data:
        st.error("A aba 'games' não foi encontrada no roster.xlsx.")
        st.stop()
    if "teams" not in data:
        st.error("A aba 'teams' não foi encontrada no roster.xlsx.")
        st.stop()

    games_df = data["games"].copy()
    teams_df = data["teams"].copy()

    required_cols = {
        "id_jogo",
        "id_time_1",
        "nome_time_1",
        "pontos_time_1",
        "pontos_time_2",
        "id_time_2",
        "nome_time_2",
    }
    missing_cols = required_cols - set(games_df.columns)
    if missing_cols:
        st.error(f"Colunas ausentes na aba games: {', '.join(sorted(missing_cols))}")
        st.stop()

    bundle = build_classification_bundle(games_df, teams_df)

    tabs = st.tabs(["Classificação", "Confronto direto", "Calendário"])
    with tabs[0]:
        render_classificacao_principal(bundle.standings)
        render_playoffs_eliminados(bundle.standings)
    with tabs[1]:
        render_confronto_tab(bundle.head_to_head_matrix)
    with tabs[2]:
        render_calendario_tab(bundle.schedule_check, games_df)


if __name__ == "__main__":
    main()