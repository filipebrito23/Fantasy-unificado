from pathlib import Path

import pandas as pd
import streamlit as st

from data_loader import load_workbook_data

DEFAULT_FILE = Path("roster.xlsx")
GAMES_SHEET = "games"


def require_login_v5():
    if "user_v5" not in st.session_state or not st.session_state.user_v5:
        st.warning("Faça login para acessar esta página.")
        st.stop()
    return st.session_state.user_v5


@st.cache_data
def cached_load(file_path: str):
    return load_workbook_data(file_path)


def build_team_lookup(teams_df: pd.DataFrame) -> pd.DataFrame:
    cols = [c for c in ["team_id", "team_name"] if c in teams_df.columns]
    return (
        teams_df[cols]
        .drop_duplicates()
        .sort_values("team_name")
        .reset_index(drop=True)
    )


def build_games_long(games_df: pd.DataFrame) -> pd.DataFrame:
    if games_df.empty:
        return pd.DataFrame()

    base_cols = [
        "id_jogo",
        "id_time_1",
        "nome_time_1",
        "pontos_time_1",
        "pontos_time_2",
        "id_time_2",
        "nome_time_2",
    ]
    df = games_df[base_cols].copy()

    team1 = pd.DataFrame(
        {
            "id_jogo": df["id_jogo"],
            "team_id": df["id_time_1"],
            "team_name": df["nome_time_1"],
            "opp_team_id": df["id_time_2"],
            "opp_team_name": df["nome_time_2"],
            "pts_for": df["pontos_time_1"],
            "pts_against": df["pontos_time_2"],
        }
    )

    team2 = pd.DataFrame(
        {
            "id_jogo": df["id_jogo"],
            "team_id": df["id_time_2"],
            "team_name": df["nome_time_2"],
            "opp_team_id": df["id_time_1"],
            "opp_team_name": df["nome_time_1"],
            "pts_for": df["pontos_time_2"],
            "pts_against": df["pontos_time_1"],
        }
    )

    long_df = pd.concat([team1, team2], ignore_index=True)
    long_df["win"] = (long_df["pts_for"] > long_df["pts_against"]).astype(int)
    long_df["loss"] = (long_df["pts_for"] < long_df["pts_against"]).astype(int)

    return long_df


def build_standings(games_df: pd.DataFrame, teams_df: pd.DataFrame) -> pd.DataFrame:
    teams_lookup = (
        build_team_lookup(teams_df)
        .rename(columns={"team_name": "Time"})
        .copy()
    )

    if games_df.empty:
        out = teams_lookup.copy()
        out["Vitórias"] = 0
        out["Derrotas"] = 0
        return out[["Time", "Vitórias", "Derrotas"]]

    long_df = build_games_long(games_df)

    standings = (
        long_df.groupby(["team_id", "team_name"], as_index=False)
        .agg({"win": "sum", "loss": "sum"})
        .rename(
            columns={
                "team_name": "Time_jogos",
                "win": "Vitórias",
                "loss": "Derrotas",
            }
        )
    )

    standings = teams_lookup.merge(
        standings[["team_id", "Vitórias", "Derrotas"]],
        on="team_id",
        how="left",
    )

    standings["Vitórias"] = standings["Vitórias"].fillna(0).astype(int)
    standings["Derrotas"] = standings["Derrotas"].fillna(0).astype(int)

    standings = standings[["team_id", "Time", "Vitórias", "Derrotas"]]

    standings = apply_head_to_head_tiebreak(standings, games_df)

    return standings[["Time", "Vitórias", "Derrotas"]]


def head_to_head_record(games_df: pd.DataFrame, team_a: int, team_b: int) -> tuple[int, int]:
    if games_df.empty:
        return (0, 0)

    subset = games_df[
        (
            (games_df["id_time_1"] == team_a) & (games_df["id_time_2"] == team_b)
        )
        | (
            (games_df["id_time_1"] == team_b) & (games_df["id_time_2"] == team_a)
        )
    ].copy()

    wins_a = 0
    wins_b = 0

    for _, row in subset.iterrows():
        if row["id_time_1"] == team_a:
            pts_a = row["pontos_time_1"]
            pts_b = row["pontos_time_2"]
        else:
            pts_a = row["pontos_time_2"]
            pts_b = row["pontos_time_1"]

        if pts_a > pts_b:
            wins_a += 1
        elif pts_b > pts_a:
            wins_b += 1

    return wins_a, wins_b


def apply_head_to_head_tiebreak(standings: pd.DataFrame, games_df: pd.DataFrame) -> pd.DataFrame:
    standings = standings.copy()
    standings = standings.sort_values(
        by=["Vitórias", "Derrotas", "Time"],
        ascending=[False, True, True],
    ).reset_index(drop=True)

    i = 0
    ordered_rows = []

    while i < len(standings):
        current = standings.iloc[i]
        tied_group = [current]

        j = i + 1
        while j < len(standings):
            other = standings.iloc[j]
            if (
                other["Vitórias"] == current["Vitórias"]
                and other["Derrotas"] == current["Derrotas"]
            ):
                tied_group.append(other)
                j += 1
            else:
                break

        if len(tied_group) == 2:
            a = tied_group[0]
            b = tied_group[1]
            wins_a, wins_b = head_to_head_record(games_df, int(a["team_id"]), int(b["team_id"]))

            if wins_b > wins_a:
                tied_group = [b, a]

        elif len(tied_group) > 2:
            tied_group = sorted(tied_group, key=lambda r: r["Time"])

        ordered_rows.extend(tied_group)
        i = j

    out = pd.DataFrame(ordered_rows).reset_index(drop=True)
    return out


def build_head_to_head_matrix(games_df: pd.DataFrame, teams_df: pd.DataFrame) -> pd.DataFrame:
    teams_lookup = build_team_lookup(teams_df)
    names = teams_lookup["team_name"].tolist()
    ids = teams_lookup["team_id"].tolist()

    matrix = pd.DataFrame("-", index=names, columns=names)

    for i, team_a in enumerate(ids):
        for j, team_b in enumerate(ids):
            name_a = teams_lookup.loc[teams_lookup["team_id"] == team_a, "team_name"].iloc[0]
            name_b = teams_lookup.loc[teams_lookup["team_id"] == team_b, "team_name"].iloc[0]

            if team_a == team_b:
                matrix.loc[name_a, name_b] = "-"
            else:
                wins_a, wins_b = head_to_head_record(games_df, int(team_a), int(team_b))
                matrix.loc[name_a, name_b] = f"{wins_a}-{wins_b}"

    matrix = matrix.reset_index().rename(columns={"index": "Time"})
    return matrix


def validate_schedule(games_df: pd.DataFrame) -> pd.DataFrame:
    if games_df.empty:
        return pd.DataFrame(columns=["Time A", "Time B", "Jogos"])

    pairs = games_df.copy()
    pairs["team_low"] = pairs[["id_time_1", "id_time_2"]].min(axis=1)
    pairs["team_high"] = pairs[["id_time_1", "id_time_2"]].max(axis=1)

    counts = (
        pairs.groupby(["team_low", "team_high"], as_index=False)
        .size()
        .rename(columns={"size": "Jogos"})
    )

    return counts


user = require_login_v5()

st.title("Classificação")
st.caption("Classificação, calendário e matchups atualizados para a temporada")

if not DEFAULT_FILE.exists():
    st.error("Arquivo roster.xlsx não encontrado na pasta do projeto.")
    st.stop()

data = cached_load(str(DEFAULT_FILE))

if "games" not in data:
    st.error("A aba 'games' não foi encontrada no roster.xlsx.")
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

standings_df = build_standings(games_df, teams_df)
matrix_df = build_head_to_head_matrix(games_df, teams_df)
schedule_check_df = validate_schedule(games_df)

st.subheader("Tabela de classificação")
st.dataframe(standings_df, use_container_width=True, hide_index=True)

st.subheader("Matriz de confronto direto")
st.dataframe(matrix_df, use_container_width=True, hide_index=True)

