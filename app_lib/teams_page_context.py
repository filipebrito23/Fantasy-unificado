import pandas as pd

from app_lib.transforms import (
    get_team_options,
    get_visible_seasons,
    build_roster_view,
    format_roster_for_display,
    calculate_main_totals,
    calculate_dev_totals,
    summarize_positions,
    summarize_picks_by_year,
)
from app_lib.transactions_service import (
    TX_SHEET,
    TX_ITEMS_SHEET,
    build_transactions_history,
)
from app_lib.teams_ui_helpers import build_red_flags


def _build_team_lookup(teams_df: pd.DataFrame) -> dict:
    if teams_df.empty or not {"team_id", "team_name"}.issubset(teams_df.columns):
        return {}

    team_map = teams_df[["team_id", "team_name"]].drop_duplicates()
    return dict(zip(team_map["team_id"], team_map["team_name"]))


def _build_player_lookup(players_df: pd.DataFrame) -> dict:
    if players_df.empty or not {"player_id", "player_name"}.issubset(players_df.columns):
        return {}

    return dict(zip(players_df["player_id"], players_df["player_name"]))


def _format_positions_text(counts: dict) -> str:
    if not counts:
        return "-"
    return " | ".join([f"{pos}: {qty}" for pos, qty in counts.items()])


def _build_picks_display(team_picks_df: pd.DataFrame, team_lookup: dict) -> pd.DataFrame:
    if team_picks_df.empty:
        return team_picks_df.copy()

    picks_display = team_picks_df.copy()

    if "original_team_pick_id" in picks_display.columns:
        picks_display["Time original"] = (
            picks_display["original_team_pick_id"]
            .map(team_lookup)
            .fillna(picks_display["original_team_pick_id"])
        )

    if "current_team_owner_id" in picks_display.columns:
        picks_display["Time atual"] = (
            picks_display["current_team_owner_id"]
            .map(team_lookup)
            .fillna(picks_display["current_team_owner_id"])
        )

    rename_map = {
        "pick_id": "Pick",
        "year": "Ano",
        "round": "Round",
    }

    return picks_display.rename(columns=rename_map)


def _get_cap_status(cap_remaining: float) -> str:
    if pd.isna(cap_remaining):
        cap_remaining = 0.0

    if cap_remaining < 0:
        return "🔴 Cap estourado"
    if cap_remaining <= 5_000_000:
        return "🟡 Cap apertado"
    return "🟢 Cap confortável"


def build_teams_page_context(data: dict, selected_team_name: str, selected_start_season: str) -> dict:
    teams = get_team_options(data["teams"])

    selected_team_id = int(
        teams.loc[teams["team_name"] == selected_team_name, "team_id"].iloc[0]
    )

    visible_seasons = get_visible_seasons(selected_start_season)

    team_lookup = _build_team_lookup(data["teams"])
    player_lookup = _build_player_lookup(data["players"])

    main_team_df = data["roster"].loc[data["roster"]["team_id"] == selected_team_id].copy()
    dev_team_df = data["development"].loc[data["development"]["team_id"] == selected_team_id].copy()

    main_roster_raw = build_roster_view(
        main_team_df, data["players"], selected_team_id, "MAIN", visible_seasons
    )
    main_roster = format_roster_for_display(main_roster_raw, visible_seasons)
    display_main = build_red_flags(main_roster, visible_seasons)
    main_totals = calculate_main_totals(
        main_team_df, data["fines"], selected_team_id, visible_seasons
    )

    dev_roster_raw = build_roster_view(
        dev_team_df, data["players"], selected_team_id, "DEV", visible_seasons
    )
    dev_roster = format_roster_for_display(dev_roster_raw, visible_seasons)
    display_dev = build_red_flags(dev_roster, visible_seasons)
    dev_totals = calculate_dev_totals(dev_team_df, visible_seasons)

    main_position_counts = summarize_positions(main_roster)
    dev_position_counts = summarize_positions(dev_roster)

    main_positions_text = _format_positions_text(main_position_counts)
    dev_positions_text = _format_positions_text(dev_position_counts)

    picks_df = data.get("picks", pd.DataFrame())
    team_picks_df = (
        picks_df.loc[picks_df["current_team_owner_id"] == selected_team_id].copy()
        if not picks_df.empty and "current_team_owner_id" in picks_df.columns
        else pd.DataFrame()
    )
    pick_year_counts = summarize_picks_by_year(team_picks_df)
    picks_display = _build_picks_display(team_picks_df, team_lookup)
    total_picks = len(team_picks_df)

    transactions_df = data.get(TX_SHEET, pd.DataFrame())
    transaction_items_df = data.get(TX_ITEMS_SHEET, pd.DataFrame())

    team_transactions_df = build_transactions_history(
        transactions_df,
        transaction_items_df,
        selected_team_id,
        team_lookup,
        player_lookup,
    )

    main_summary = main_totals.iloc[0].to_dict() if not main_totals.empty else {}

    cap_remaining = pd.to_numeric(
        pd.Series([main_summary.get("Cap restante", 0.0)]),
        errors="coerce"
    ).iloc[0]

    if pd.isna(cap_remaining):
        cap_remaining = 0.0

    cap_status = _get_cap_status(cap_remaining)

    return {
        "teams": teams,
        "selected_team_id": selected_team_id,
        "selected_team_name": selected_team_name,
        "selected_start_season": selected_start_season,
        "visible_seasons": visible_seasons,
        "team_lookup": team_lookup,
        "player_lookup": player_lookup,
        "main_team_df": main_team_df,
        "dev_team_df": dev_team_df,
        "main_roster_raw": main_roster_raw,
        "main_roster": main_roster,
        "display_main": display_main,
        "main_totals": main_totals,
        "dev_roster_raw": dev_roster_raw,
        "dev_roster": dev_roster,
        "display_dev": display_dev,
        "dev_totals": dev_totals,
        "main_position_counts": main_position_counts,
        "dev_position_counts": dev_position_counts,
        "main_positions_text": main_positions_text,
        "dev_positions_text": dev_positions_text,
        "team_picks_df": team_picks_df,
        "picks_display": picks_display,
        "pick_year_counts": pick_year_counts,
        "total_picks": total_picks,
        "team_transactions_df": team_transactions_df,
        "main_summary": main_summary,
        "cap_remaining": cap_remaining,
        "cap_status": cap_status,
    }