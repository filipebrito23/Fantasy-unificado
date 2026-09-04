from __future__ import annotations

import matplotlib.pyplot as plt
import pandas as pd
import streamlit as st

from app_lib.fantasy_data_service import load_fantasy_data_from_neon
from app_lib.standings_service import build_classification_bundle

PLAYOFF_SPOTS = 8
ELIMINATED_SPOTS = 6

@st.cache_data(ttl=60, show_spinner=False)
def cached_load():
    """
    Carrega a base de Classificação a partir do Neon.

    Retorna o mesmo contrato antes obtido de load_workbook_data('roster.xlsx'):
    data["teams"], data["games"], etc.
    """
    return load_fantasy_data_from_neon()


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
    st.subheader("Calendário")
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


def render_agenda_tab(data: dict[str, pd.DataFrame]) -> None:
    """
    Agenda NBA por semana e por time.
    Colunas esperadas na aba 'Semana': SEMANANUM, TEAMABBR, JOGONASEMANA, GAMEDATE
    """
    st.subheader("Agenda NBA")
    st.caption("Jogos por semana e por time")

    semana_df = data.get("Semana", pd.DataFrame())
    if semana_df.empty:
        st.info("Nenhuma agenda semanal carregada (aba 'Semana' vazia ou ausente no roster.xlsx).")
        return

    df = semana_df.copy()
    df.columns = [str(c).strip().upper() for c in df.columns]

    required = {"SEMANANUM", "TEAMABBR", "JOGONASEMANA", "GAMEDATE"}
    if not required.issubset(set(df.columns)):
        st.warning("Colunas necessárias não encontradas na aba 'Semana' (esperado: SEMANANUM, TEAMABBR, JOGONASEMANA, GAMEDATE).")
        st.dataframe(df.head(), use_container_width=True, hide_index=True)
        return

    df["GAMEDATE"] = pd.to_datetime(df["GAMEDATE"], errors="coerce")
    df = df.sort_values(["SEMANANUM", "TEAMABBR", "JOGONASEMANA", "GAMEDATE"])

    weeks = df.groupby("SEMANANUM")

    for semana_num, g in weeks:
        semana_label = f"Semana {int(semana_num)}"
        with st.expander(semana_label, expanded=False):
            # Agrupa por time dentro da semana
            for team, tg in g.groupby("TEAMABBR"):
                with st.expander(f"{team}", expanded=False):
                    show = tg[["JOGONASEMANA", "GAMEDATE"]].copy()
                    show = show.rename(columns={
                        "JOGONASEMANA": "Jogo_na_semana",
                        "GAMEDATE": "Data",
                    })
                    show["Data"] = show["Data"].dt.date
                    st.dataframe(show, use_container_width=True, hide_index=True)


def main():
    st.title("Classificacao")
    st.caption("Classificacao, confronto direto e calendario da temporada")

    data = cached_load()

    # A função load_fantasy_data_from_neon já retorna as chaves "games" e "teams"
    # no mesmo formato antes obtido via load_workbook_data('roster.xlsx').
    games_df = data.get("games", pd.DataFrame())
    teams_df = data.get("teams", pd.DataFrame())

    if games_df.empty:
        st.info("Nenhum jogo encontrado na base de Classificação.")
        # Ainda permitimos mostrar a tabela de times vazia ou com 0 vitórias/derrotas
    bundle = build_classification_bundle(games_df, teams_df)

    tabs = st.tabs([
        "Classificacao",
        "Confronto direto",
        "Calendario",
        "Agenda NBA",
    ])

    with tabs[0]:
        render_classificacao_principal(bundle.standings)
        render_playoffs_eliminados(bundle.standings)

    with tabs[1]:
        render_confronto_tab(bundle.head_to_head_matrix)

    with tabs[2]:
        render_calendario_tab(bundle.schedule_check, games_df)

    with tabs[3]:
        render_agenda_tab(data)
        return

    required_cols = {
        "id_jogo",
        "id_time_1",
        "nome_time_1",
        "pontos_time_1",
        "pontos_time_2",
        "id_time_2",
        "nome_time_2",
        "rodada",
    }

    missing_cols = required_cols - set(games_df.columns)
    if missing_cols:
        st.error(f"Colunas ausentes na base de jogos: {', '.join(sorted(missing_cols))}")
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