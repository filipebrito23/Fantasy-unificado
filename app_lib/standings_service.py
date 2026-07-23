from __future__ import annotations

from dataclasses import dataclass

import pandas as pd


@dataclass
class StandingsResult:
    standings: pd.DataFrame
    head_to_head_matrix: pd.DataFrame
    schedule_check: pd.DataFrame


def build_team_lookup(teams_df: pd.DataFrame) -> pd.DataFrame:
    cols = [c for c in ["team_id", "team_name"] if c in teams_df.columns]
    return teams_df[cols].drop_duplicates().sort_values("team_name").reset_index(drop=True)


def build_games_long(games_df: pd.DataFrame) -> pd.DataFrame:
    if games_df.empty:
        return pd.DataFrame()
    df = games_df[["id_jogo", "id_time_1", "nome_time_1", "pontos_time_1", "pontos_time_2", "id_time_2", "nome_time_2"]].copy()
    team1 = pd.DataFrame({
        "id_jogo": df["id_jogo"], "team_id": df["id_time_1"], "Time": df["nome_time_1"],
        "opp_team_id": df["id_time_2"], "opp_team_name": df["nome_time_2"],
        "pts_for": df["pontos_time_1"], "pts_against": df["pontos_time_2"],
    })
    team2 = pd.DataFrame({
        "id_jogo": df["id_jogo"], "team_id": df["id_time_2"], "Time": df["nome_time_2"],
        "opp_team_id": df["id_time_1"], "opp_team_name": df["nome_time_1"],
        "pts_for": df["pontos_time_2"], "pts_against": df["pontos_time_1"],
    })
    long_df = pd.concat([team1, team2], ignore_index=True)
    long_df["win"] = (long_df["pts_for"] > long_df["pts_against"]).astype(int)
    long_df["loss"] = (long_df["pts_for"] < long_df["pts_against"]).astype(int)
    long_df["tie"] = (long_df["pts_for"] == long_df["pts_against"]).astype(int)
    long_df["points_diff"] = long_df["pts_for"] - long_df["pts_against"]
    return long_df


def head_to_head_record(games_df: pd.DataFrame, team_a: int, team_b: int) -> tuple[int, int]:
    if games_df.empty:
        return (0, 0)
    subset = games_df[((games_df["id_time_1"] == team_a) & (games_df["id_time_2"] == team_b)) | ((games_df["id_time_1"] == team_b) & (games_df["id_time_2"] == team_a))].copy()
    wins_a = wins_b = 0
    for _, row in subset.iterrows():
        if row["id_time_1"] == team_a:
            pts_a, pts_b = row["pontos_time_1"], row["pontos_time_2"]
        else:
            pts_a, pts_b = row["pontos_time_2"], row["pontos_time_1"]
        if pts_a > pts_b:
            wins_a += 1
        elif pts_b > pts_a:
            wins_b += 1
    return wins_a, wins_b


def apply_head_to_head_tiebreak(standings: pd.DataFrame, games_df: pd.DataFrame) -> pd.DataFrame:
    if standings.empty:
        return standings
    standings = standings.copy()
    if "Time" not in standings.columns and "team_name" in standings.columns:
        standings = standings.rename(columns={"team_name": "Time"})
    if "Time" not in standings.columns:
        standings["Time"] = standings["team_id"].astype(str)
    standings = standings.sort_values(["Vitórias", "Saldo", "Aproveitamento", "Time"], ascending=[False, False, False, True]).reset_index(drop=True)
    ordered_rows = []
    i = 0
    while i < len(standings):
        current = standings.iloc[i]
        tied_group = [current]
        j = i + 1
        while j < len(standings):
            other = standings.iloc[j]
            if other["Vitórias"] == current["Vitórias"] and other["Saldo"] == current["Saldo"] and other["Aproveitamento"] == current["Aproveitamento"]:
                tied_group.append(other)
                j += 1
            else:
                break
        if len(tied_group) == 2:
            a, b = tied_group
            wins_a, wins_b = head_to_head_record(games_df, int(a["team_id"]), int(b["team_id"]))
            if wins_b > wins_a:
                tied_group = [b, a]
        elif len(tied_group) > 2:
            tied_ids = {int(x["team_id"]) for x in tied_group}
            mini = []
            for row in tied_group:
                team_id = int(row["team_id"])
                wins = 0
                losses = 0
                for opp_id in tied_ids:
                    if opp_id == team_id:
                        continue
                    wa, wb = head_to_head_record(games_df, team_id, opp_id)
                    wins += wa
                    losses += wb
                mini.append((row, wins, losses))
            tied_group = [x[0] for x in sorted(mini, key=lambda t: (-t[1], t[2], str(t[0].get("Time", ""))))]
        ordered_rows.extend(tied_group)
        i = j
    out = pd.DataFrame(ordered_rows).reset_index(drop=True)
    if "Time" not in out.columns and "team_name" in out.columns:
        out = out.rename(columns={"team_name": "Time"})
    if "Time" not in out.columns:
        out["Time"] = out["team_id"].astype(str)
    return out


def build_standings(games_df: pd.DataFrame, teams_df: pd.DataFrame) -> pd.DataFrame:
    teams_lookup = build_team_lookup(teams_df).rename(columns={"team_name": "Time"}).copy()
    if games_df.empty:
        out = teams_lookup.copy()
        out[["Jogos", "Vitórias", "Derrotas", "Empates", "Saldo", "Pontos a favor", "Pontos contra"]] = 0
        out["Aproveitamento"] = "0%"
        out["Posição"] = range(1, len(out) + 1)
        return out[["Posição", "Time", "Jogos", "Vitórias", "Derrotas", "Empates", "Saldo", "Pontos a favor", "Pontos contra", "Aproveitamento"]]
    long_df = build_games_long(games_df)
    agg = long_df.groupby(["team_id", "Time"], as_index=False).agg({"win": "sum", "loss": "sum", "tie": "sum", "pts_for": "sum", "pts_against": "sum", "points_diff": "sum", "id_jogo": pd.Series.nunique}).rename(columns={"win": "Vitórias", "loss": "Derrotas", "tie": "Empates", "pts_for": "Pontos a favor", "pts_against": "Pontos contra", "points_diff": "Saldo", "id_jogo": "Jogos"})
    standings = teams_lookup.merge(agg, on="team_id", how="left")
    if "Time_x" in standings.columns or "Time_y" in standings.columns:
        tx = standings.pop("Time_x") if "Time_x" in standings.columns else None
        ty = standings.pop("Time_y") if "Time_y" in standings.columns else None
        standings["Time"] = tx if tx is not None else ty
        if tx is not None and ty is not None:
            standings["Time"] = tx.combine_first(ty)
    if "Time" not in standings.columns:
        standings["Time"] = standings["team_id"].astype(str)
    for col in ["Jogos", "Vitórias", "Derrotas", "Empates", "Pontos a favor", "Pontos contra", "Saldo"]:
        standings[col] = standings[col].fillna(0).astype(int)
    total_games = standings["Jogos"].where(standings["Jogos"] > 0, 1)
    pct = ((standings["Vitórias"] + 0.5 * standings["Empates"]) / (2 * total_games) * 100).round(1)
    standings["Aproveitamento"] = pct.map(lambda x: f"{x:.1f}%")
    standings = apply_head_to_head_tiebreak(standings, games_df).reset_index(drop=True)
    standings["Posição"] = standings.index + 1
    return standings[["Posição", "Time", "Jogos", "Vitórias", "Derrotas", "Empates", "Saldo", "Pontos a favor", "Pontos contra", "Aproveitamento"]]


def build_head_to_head_matrix(games_df: pd.DataFrame, teams_df: pd.DataFrame) -> pd.DataFrame:
    teams_lookup = build_team_lookup(teams_df)
    names = teams_lookup["team_name"].tolist()
    ids = teams_lookup["team_id"].tolist()
    matrix = pd.DataFrame("-", index=names, columns=names)
    for team_a in ids:
        name_a = teams_lookup.loc[teams_lookup["team_id"] == team_a, "team_name"].iloc[0]
        for team_b in ids:
            name_b = teams_lookup.loc[teams_lookup["team_id"] == team_b, "team_name"].iloc[0]
            if team_a == team_b:
                matrix.loc[name_a, name_b] = "-"
            else:
                wa, wb = head_to_head_record(games_df, int(team_a), int(team_b))
                matrix.loc[name_a, name_b] = f"{wa}-{wb}"
    return matrix.reset_index().rename(columns={"index": "Time"})


def validate_schedule(games_df: pd.DataFrame, teams_df: pd.DataFrame) -> pd.DataFrame:
    if games_df.empty:
        return pd.DataFrame(columns=["Time A", "Time B", "Jogos"])
    lookup = build_team_lookup(teams_df).set_index("team_id")["team_name"].to_dict()
    pairs = games_df.copy()
    pairs["team_low"] = pairs[["id_time_1", "id_time_2"]].min(axis=1)
    pairs["team_high"] = pairs[["id_time_1", "id_time_2"]].max(axis=1)
    counts = pairs.groupby(["team_low", "team_high"], as_index=False).size().rename(columns={"size": "Jogos"})
    counts["Time A"] = counts["team_low"].map(lookup)
    counts["Time B"] = counts["team_high"].map(lookup)
    return counts[["Time A", "Time B", "Jogos"]].sort_values(["Jogos", "Time A", "Time B"], ascending=[False, True, True]).reset_index(drop=True)


def build_classification_bundle(games_df: pd.DataFrame, teams_df: pd.DataFrame) -> StandingsResult:
    standings = build_standings(games_df, teams_df)
    matrix = build_head_to_head_matrix(games_df, teams_df)
    schedule_check = validate_schedule(games_df, teams_df)
    return StandingsResult(standings=standings, head_to_head_matrix=matrix, schedule_check=schedule_check)