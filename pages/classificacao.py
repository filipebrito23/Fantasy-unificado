from __future__ import annotations


from pathlib import Path

import matplotlib.pyplot as plt
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
    st.subheader("Classificacao")
    st.caption(f"Top {PLAYOFF_SPOTS} avancam para os playoffs. Os ultimos {ELIMINATED_SPOTS} sao eliminados.")
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
    """
    Matriz analítica de confronto direto.
    """
    import matplotlib.pyplot as plt
    import numpy as np

    st.subheader("Confronto direto")
    st.caption("Matriz analítica do retrospecto entre os times")

    if matrix_df.empty or "Time" not in matrix_df.columns:
        st.info("Sem dados de confronto direto.")
        return

    teams = matrix_df["Time"].tolist()
    mtx = matrix_df.drop(columns=["Time"]).to_numpy(dtype=object)

    def parse_record(cell):
        if cell == "-":
            return 0
        try:
            w, l = str(cell).split("-")
            return int(w) - int(l)
        except Exception:
            return 0

    numeric = np.vectorize(parse_record)(mtx)

    fig, ax = plt.subplots(figsize=(10, 8))
    cmap = plt.cm.RdYlGn
    norm = plt.Normalize(vmin=numeric.min(), vmax=numeric.max())
    im = ax.imshow(numeric, cmap=cmap, norm=norm)

    ax.set_xticks(range(len(teams)))
    ax.set_yticks(range(len(teams)))
    ax.set_xticklabels(teams, rotation=45, ha="right")
    ax.set_yticklabels(teams)

    for i in range(len(teams)):
        for j in range(len(teams)):
            text = mtx[i, j]
            ax.text(j, i, text, ha="center", va="center", color="black")

    fig.colorbar(im, ax=ax, label="Saldo (Vitórias - Derrotas)")
    ax.set_title("Matriz de confronto direto")
    st.pyplot(fig)

def render_calendario_tab(schedule_check_df: pd.DataFrame, games_df: pd.DataFrame):
    st.subheader("Calendario")
    st.caption("Linha do tempo da temporada")

    # Narrativa por semana/rodada
    if not games_df.empty and "rodada" in games_df.columns:
        for rodada in sorted(games_df["rodada"].dropna().unique()):
            rodada_df = games_df[games_df["rodada"] == rodada].copy()
            with st.expander(f"Rodada {rodada}", expanded=False):
                cols = [c for c in rodada_df.columns if c not in {"id_jogo", "id_time_1", "id_time_2"}]
                st.table(rodada_df[cols] if cols else rodada_df)
    else:
        with st.expander("Jogos", expanded=False):
            cols = [c for c in games_df.columns if c not in {"id_jogo", "id_time_1", "id_time_2"}]
            st.table(games_df[cols] if cols else games_df)

    with st.expander("Validacao do calendario", expanded=False):
        if schedule_check_df.empty:
            st.info("Sem jogos para validar.")
        else:
            st.dataframe(schedule_check_df, use_container_width=True, hide_index=True)


def main():
    st.title("Classificacao")
    st.caption("Classificacao, confronto direto e calendario da temporada")

    if not DEFAULT_FILE.exists():
        st.error("Arquivo roster.xlsx nao encontrado na pasta do projeto.")
        st.stop()

    data = cached_load(str(DEFAULT_FILE))
    if "games" not in data:
        st.error("A aba 'games' nao foi encontrada no roster.xlsx.")
        st.stop()
    if "teams" not in data:
        st.error("A aba 'teams' nao foi encontrada no roster.xlsx.")
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
        "rodada"
    }
    missing_cols = required_cols - set(games_df.columns)
    if missing_cols:
        st.error(f"Colunas ausentes na aba games: {', '.join(sorted(missing_cols))}")
        st.stop()

    bundle = build_classification_bundle(games_df, teams_df)

    tabs = st.tabs(["Classificacao", "Confronto direto", "Calendario"])
    with tabs[0]:
        render_classificacao_principal(bundle.standings)
        render_playoffs_eliminados(bundle.standings)
    with tabs[1]:
        render_confronto_tab(bundle.head_to_head_matrix)
    with tabs[2]:
        render_calendario_tab(bundle.schedule_check, games_df)


if __name__ == "__main__":
    main()
