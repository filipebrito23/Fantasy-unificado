import pandas as pd
from data_loader import SEASONS, FINE_COLS

SEASON_LABELS = {
    "26_27": "2026-27",
    "27_28": "2027-28",
    "28_29": "2028-29",
    "29_30": "2029-30",
}


def get_team_options(teams: pd.DataFrame) -> pd.DataFrame:
    cols = [c for c in ["team_id", "team_name"] if c in teams.columns]
    return teams[cols].drop_duplicates().sort_values("team_name").reset_index(drop=True)


def get_visible_seasons(start_season: str) -> list[str]:
    idx = SEASONS.index(start_season)
    return SEASONS[idx:]


def _player_lookup(players_df: pd.DataFrame) -> pd.DataFrame:
    cols = [c for c in ["player_id", "player_name", "position", "nba_team"] if c in players_df.columns]
    return players_df[cols].drop_duplicates(subset=["player_id"])


def build_roster_view(roster_df: pd.DataFrame, players_df: pd.DataFrame, team_id: int, roster_type: str, visible_seasons: list[str]) -> pd.DataFrame:
    df = roster_df.loc[roster_df["team_id"] == team_id].copy()
    df = df.merge(_player_lookup(players_df), on="player_id", how="left")
    order_col = "pos_order" if "pos_order" in df.columns else "order"
    if order_col in df.columns:
        df = df.sort_values(order_col, na_position="last")
    base_cols = [order_col, "player_id", "player_name", "position"]
    season_cols = []
    for season in visible_seasons:
        sal_col = f"salarie_{season}"
        opt_col = f"option_{season}"
        if sal_col in df.columns:
            season_cols.append(sal_col)
        if opt_col in df.columns:
            season_cols.append(opt_col)
    visible_cols = [c for c in [*base_cols, *season_cols] if c in df.columns]
    df = df[visible_cols].copy()
    df.insert(0, "roster_type", roster_type)
    return df.reset_index(drop=True)


def format_roster_for_display(df: pd.DataFrame, visible_seasons: list[str]) -> pd.DataFrame:
    out = df.copy()
    rename_map = {
        "roster_type": "Tipo",
        "pos_order": "Ordem",
        "order": "Ordem",
        "player_id": "Player ID",
        "player_name": "Jogador",
        "position": "Posição",
    }
    for season in visible_seasons:
        rename_map[f"salarie_{season}"] = SEASON_LABELS[season]
    return out.rename(columns=rename_map)


def get_team_fines_row(fines_df: pd.DataFrame, team_id: int) -> dict:
    team_fines = fines_df.loc[fines_df["team_id"] == team_id]
    if team_fines.empty:
        return {"team_id": team_id, **{c: 0.0 for c in FINE_COLS}, "notes": ""}
    row = team_fines.iloc[0].to_dict()
    for col in FINE_COLS:
        row[col] = 0.0 if pd.isna(row.get(col)) else float(row.get(col, 0.0))
    return row


def calculate_main_totals(main_roster_df: pd.DataFrame, fines_df: pd.DataFrame, team_id: int, visible_seasons: list[str]) -> pd.DataFrame:
    fines_row = get_team_fines_row(fines_df, team_id)
    rows = []
    for season in visible_seasons:
        sal_col = f"salarie_{season}"
        fine_col = f"fine_{season}"
        total_salary = float(main_roster_df[sal_col].fillna(0).sum()) if sal_col in main_roster_df.columns else 0.0
        total_fine = float(fines_row.get(fine_col, 0.0))
        cap_space = 110_000_000 - total_salary - total_fine
        rows.append({"Temporada": SEASON_LABELS[season], "Salários": total_salary, "Multas": total_fine, "Cap restante": cap_space})
    return pd.DataFrame(rows)


def calculate_dev_totals(dev_df: pd.DataFrame, visible_seasons: list[str]) -> pd.DataFrame:
    rows = []
    for season in visible_seasons:
        sal_col = f"salarie_{season}"
        total_salary = float(dev_df[sal_col].fillna(0).sum()) if sal_col in dev_df.columns else 0.0
        cap_space = 14_000_000 - total_salary
        rows.append({"Temporada": SEASON_LABELS[season], "Salários": total_salary, "Cap restante": cap_space})
    return pd.DataFrame(rows)
