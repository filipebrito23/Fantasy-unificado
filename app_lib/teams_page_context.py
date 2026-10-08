import os
import pandas as pd
import streamlit as st
from app_lib.season_config import (
    ACTIVE_SEASON,
    SEASONS,
    SEASON_LABELS,
)
from app_lib.transforms import (
    get_team_options,
    get_visible_seasons,
    summarize_picks_by_year,
)
from app_lib.roster_service import (get_team_picks,get_team_roster,get_team_roster_positions,get_team_roster_totals,get_team_fines,)
from app_lib.transactions_service import (build_transactions_history,get_team_transactions_history_neon,format_team_transactions_history,)
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


def _build_picks_display(
    team_picks_df: pd.DataFrame,
    team_lookup: dict,
) -> pd.DataFrame:
    if team_picks_df.empty:
        return team_picks_df.copy()

    picks_display = team_picks_df.copy()

    if "original_team_name" in picks_display.columns:
        picks_display["Time original"] = (
            picks_display["original_team_name"]
        )

    elif "original_team_pick_id" in picks_display.columns:
        picks_display["Time original"] = (
            picks_display[
                "original_team_pick_id"
            ]
            .map(team_lookup)
            .fillna(
                picks_display[
                    "original_team_pick_id"
                ]
            )
        )

    if "current_team_name" in picks_display.columns:
        picks_display["Time atual"] = (
            picks_display["current_team_name"]
        )

    elif "current_team_owner_id" in picks_display.columns:
        picks_display["Time atual"] = (
            picks_display[
                "current_team_owner_id"
            ]
            .map(team_lookup)
            .fillna(
                picks_display[
                    "current_team_owner_id"
                ]
            )
        )

    rename_map = {
        "pick_id": "Pick",
        "source_pick_id": "Pick origem",
        "year": "Ano",
        "round": "Round",
    }

    return picks_display.rename(
        columns=rename_map
    )


def _get_cap_status(cap_remaining: float) -> str:
    if pd.isna(cap_remaining):
        cap_remaining = 0.0
    if cap_remaining < 0:
        return "🔴 Cap estourado"
    if cap_remaining <= 5_000_000:
        return "🟡 Cap apertado"
    return "🟢 Cap confortável"


@st.cache_data(show_spinner=False)
def _cached_team_transactions_history(
    tx_mtime: float,
    items_mtime: float,
    transactions_df: pd.DataFrame,
    transaction_items_df: pd.DataFrame,
    selected_team_id: int,
    team_lookup: dict,
    player_lookup: dict,
) -> pd.DataFrame:
    return build_transactions_history(
        transactions_df,
        transaction_items_df,
        selected_team_id,
        team_lookup,
        player_lookup,
    )

def _build_normalized_roster_display(
    roster_df: pd.DataFrame,
    visible_seasons: list[str],
) -> pd.DataFrame:
    base_columns = [
        "Ordem",
        "Jogador",
        "Posição",
        "source_player_id",
    ]

    if roster_df.empty:
        columns = base_columns.copy()

        for season in visible_seasons:
            columns.extend(
                [
                    f"Salário {season}",
                    f"Option {season}",
                ]
            )

        return pd.DataFrame(columns=columns)

    working = roster_df.copy()

    for column in [
        "source_player_id",
        "player_name",
        "position",
        "roster_order",
        "salary",
        "team_option",
        "ui_season",
    ]:
        if column not in working.columns:
            working[column] = None

    working["source_player_id"] = pd.to_numeric(
        working["source_player_id"],
        errors="coerce",
    )

    working["roster_order"] = pd.to_numeric(
        working["roster_order"],
        errors="coerce",
    )

    working["salary"] = working["salary"].map(
        _to_number
    )

    working["team_option"] = (
        working["team_option"]
        .map(_to_bool)
    )

    working["ui_season"] = (
        working["ui_season"]
        .astype(str)
        .str.strip()
    )

    first_season = str(visible_seasons[0])

    base_df = working.loc[
        working["ui_season"] == first_season
    ].copy()

    base_df = base_df.sort_values(
        by=[
            "roster_order",
            "player_name",
        ],
        na_position="last",
    )

    base_df = base_df.drop_duplicates(
        subset=["source_player_id"],
        keep="first",
    )

    result = pd.DataFrame(
        {
            "Ordem": base_df[
                "roster_order"
            ].tolist(),
            "Jogador": base_df[
                "player_name"
            ].tolist(),
            "Posição": base_df[
                "position"
            ].tolist(),
            "source_player_id": base_df[
                "source_player_id"
            ].tolist(),
        }
    )

    player_ids = result[
        "source_player_id"
    ].tolist()

    for season in visible_seasons:
        season_key = str(season)

        season_df = working.loc[
            working["ui_season"] == season_key
        ].copy()

        season_df = season_df.drop_duplicates(
            subset=["source_player_id"],
            keep="first",
        )

        salary_by_player = dict(
            zip(
                season_df["source_player_id"],
                season_df["salary"],
            )
        )

        option_by_player = dict(
            zip(
                season_df["source_player_id"],
                season_df["team_option"],
            )
        )

        result[f"Salário {season_key}"] = [
            salary_by_player.get(
                player_id,
                0.0,
            )
            for player_id in player_ids
        ]

        result[f"Option {season_key}"] = [
            bool(
                option_by_player.get(
                    player_id,
                    False,
                )
            )
            for player_id in player_ids
        ]

    return result

def _format_totals_for_existing_ui(
    totals_df: pd.DataFrame,
    fines_total: float = 0.0,
    season: str | None = None,
    apply_fines: bool = True,
) -> pd.DataFrame:
    columns = [
        "Temporada",
        "Salários",
        "Multas",
        "Disponível",
        "Cap restante",
    ]

    if totals_df.empty:
        return pd.DataFrame(columns=columns)

    row = totals_df.iloc[0]

    salary_total = _to_number(
        row.get("salary_total", 0.0)
    )

    if "available" in totals_df.columns:
        available = _to_number(
            row.get("available", 0.0)
        )
    else:
        available = _to_number(
            row.get("cap_remaining", 0.0)
        )

    fines_total = _to_number(fines_total)

    if apply_fines:
        cap_remaining = available - fines_total
    else:
        cap_remaining = available

    return pd.DataFrame(
        [
            {
                "Temporada": season or "",
                "Salários": salary_total,
                "Multas": fines_total if apply_fines else 0.0,
                "Disponível": available,
                "Cap restante": cap_remaining,
            }
        ],
        columns=columns,
    )

def _normalize_season_for_db(
    season: str,
) -> str:
    value = str(season or "").strip()

    season_map = {
        "26_27": "2026-27",
        "27_28": "2027-28",
        "28_29": "2028-29",
        "29_30": "2029-30",
        "2026-27": "2026-27",
        "2027-28": "2027-28",
        "2028-29": "2028-29",
        "2029-30": "2029-30",
    }

    if value not in season_map:
        raise ValueError(
            f"Temporada não reconhecida: {season}"
        )

    return season_map[value]

def _find_column(
    df: pd.DataFrame,
    candidates: list[str],
) -> str | None:
    normalized = {
        str(column).strip().lower(): column
        for column in df.columns
    }

    for candidate in candidates:
        key = candidate.strip().lower()

        if key in normalized:
            return normalized[key]

    return None


def _to_number(value) -> float:
    if pd.isna(value):
        return 0.0

    if isinstance(value, str):
        value = (
            value.replace("R$", "")
            .replace("$", "")
            .replace(".", "")
            .replace(",", ".")
            .strip()
        )

    result = pd.to_numeric(
        value,
        errors="coerce",
    )

    return 0.0 if pd.isna(result) else float(result)


def _to_bool(value) -> bool:
    if pd.isna(value):
        return False

    if isinstance(value, bool):
        return value

    if isinstance(value, (int, float)):
        return bool(value)

    return str(value).strip().lower() in {
        "true",
        "t",
        "1",
        "yes",
        "y",
        "sim",
        "x",
        "✓",
    }


def _prepare_roster_frame(
    roster_df: pd.DataFrame,
    ui_season: str,
) -> pd.DataFrame:
    frame = roster_df.copy()

    frame["ui_season"] = str(ui_season)

    salary_column = _find_column(
        frame,
        [
            "salary",
            "salary_amount",
            "annual_salary",
            "cap_hit",
            "salario",
            "salário",
        ],
    )

    option_column = _find_column(
        frame,
        [
            "team_option",
            "team_option_flag",
            "option",
            "has_option",
            "player_option",
            "team option",
            "option_flag",
        ],
    )

    if salary_column is not None:
        frame["salary"] = frame[
            salary_column
        ].map(_to_number)
    else:
        frame["salary"] = 0.0

    if option_column is not None:
        frame["team_option"] = frame[
            option_column
        ].map(_to_bool)
    else:
        frame["team_option"] = False

    return frame


def _extract_fine_for_season(
    fines_df: pd.DataFrame,
    selected_team_id: int,
    ui_season: str,
) -> float:
    if fines_df is None or fines_df.empty:
        return 0.0

    required_columns = {
        "team_id",
        "fine_26_27",
        "fine_27_28",
        "fine_28_29",
        "fine_29_30",
    }

    missing_columns = required_columns.difference(
        fines_df.columns
    )

    if missing_columns:
        return 0.0

    fine_column_by_season = {
        "26_27": "fine_26_27",
        "27_28": "fine_27_28",
        "28_29": "fine_28_29",
        "29_30": "fine_29_30",
        "2026-27": "fine_26_27",
        "2027-28": "fine_27_28",
        "2028-29": "fine_28_29",
        "2029-30": "fine_29_30",
    }

    fine_column = fine_column_by_season.get(
        str(ui_season).strip()
    )

    if fine_column is None:
        return 0.0

    team_ids = pd.to_numeric(
        fines_df["team_id"],
        errors="coerce",
    )

    team_fines = fines_df.loc[
        team_ids == int(selected_team_id),
        fine_column,
    ]

    if team_fines.empty:
        return 0.0

    return float(
        team_fines.map(_to_number).sum()
    )

def build_teams_page_context(
    data: dict,
    selected_team_name: str,
    selected_start_season: str,
    workbook_path: str | None = None,
) -> dict:
    teams = get_team_options(data["teams"])

    selected_team_id = int(
        teams.loc[
            teams["team_name"] == selected_team_name,
            "team_id",
        ].iloc[0]
    )

    visible_seasons = get_visible_seasons(
        selected_start_season
    )

    team_lookup = _build_team_lookup(data["teams"])
    player_lookup = _build_player_lookup(
        data.get("players", pd.DataFrame())
    )

    main_frames: list[pd.DataFrame] = []
    dev_frames: list[pd.DataFrame] = []

    for current_season in visible_seasons:
        db_season = _normalize_season_for_db(
            current_season
        )

        main_current = get_team_roster(
            selected_team_id,
            db_season,
            "MAIN",
        )

        dev_current = get_team_roster(
            selected_team_id,
            db_season,
            "DEV",
        )

        main_current = _prepare_roster_frame(
            main_current,
            current_season,
        )

        dev_current = _prepare_roster_frame(
            dev_current,
            current_season,
        )

        main_frames.append(main_current)
        dev_frames.append(dev_current)

    main_team_df = (
        pd.concat(main_frames, ignore_index=True)
        if main_frames
        else pd.DataFrame()
    )

    dev_team_df = (
        pd.concat(dev_frames, ignore_index=True)
        if dev_frames
        else pd.DataFrame()
    )

    main_roster = _build_normalized_roster_display(
        main_team_df,
        visible_seasons,
    )

    dev_roster = _build_normalized_roster_display(
        dev_team_df,
        visible_seasons,
    )

    main_roster_raw = main_team_df.copy()
    dev_roster_raw = dev_team_df.copy()

    display_main = main_roster.copy()
    display_dev = dev_roster.copy()

    selected_db_season = _normalize_season_for_db(
        selected_start_season
    )

    fines_df = get_team_fines(
        selected_team_id
    )
    
    totals_by_season = {}

    for current_season in visible_seasons:
        current_db_season = _normalize_season_for_db(
            current_season
        )

        main_totals_raw = get_team_roster_totals(
            selected_team_id,
            current_db_season,
            "MAIN",
        )

        dev_totals_raw = get_team_roster_totals(
            selected_team_id,
            current_db_season,
            "DEV",
        )

        current_fines = _extract_fine_for_season(
            fines_df,
            selected_team_id,
            current_season,
        )

        main_fines = current_fines
        dev_fines = current_fines

        main_totals = _format_totals_for_existing_ui(
            main_totals_raw,
            fines_total=main_fines,
            season=current_season,
        )

        dev_totals = _format_totals_for_existing_ui(
            dev_totals_raw,
            fines_total=dev_fines,
            season=current_season,
        )

        totals_by_season[current_season] = {
            "main": main_totals,
            "dev": dev_totals,
        }

    main_position_counts = get_team_roster_positions(
        selected_team_id,
        selected_db_season,
        "MAIN",
    )

    dev_position_counts = get_team_roster_positions(
        selected_team_id,
        selected_db_season,
        "DEV",
    )

    main_positions_text = _format_positions_text(
        main_position_counts
    )

    dev_positions_text = _format_positions_text(
        dev_position_counts
    )

    selected_db_season = _normalize_season_for_db(
        selected_start_season
    )

    picks_frames = []

    for current_season in visible_seasons:
        current_db_season = _normalize_season_for_db(
            current_season
        )

        current_picks = get_team_picks(
            selected_team_id,
            current_db_season,
        )

        if not current_picks.empty:
            current_picks = current_picks.copy()
            current_picks["Temporada"] = (
                current_season
            )
            picks_frames.append(current_picks)

    team_picks_df = (
        pd.concat(
            picks_frames,
            ignore_index=True,
        )
        if picks_frames
        else pd.DataFrame()
    )

    pick_year_counts = (
        summarize_picks_by_year(team_picks_df)
        if not team_picks_df.empty
        else {}
    )

    picks_display = _build_picks_display(
        team_picks_df,
        team_lookup,
    )

    total_picks = len(team_picks_df)

    team_transactions_raw = (
        get_team_transactions_history_neon(
            selected_team_id
        )
    )

    team_transactions_df = (
        format_team_transactions_history(
            team_transactions_raw,
            selected_team_id,
        )
    )
    first_season = visible_seasons[0]

    main_totals = totals_by_season[
        first_season
    ]["main"]

    dev_totals = totals_by_season[
        first_season
    ]["dev"]

    main_summary = (
        main_totals.iloc[0].to_dict()
        if not main_totals.empty
        else {}
    )

    cap_remaining = pd.to_numeric(
        pd.Series(
            [main_summary.get(
                "Cap restante",
                0.0,
            )]
        ),
        errors="coerce",
    ).iloc[0]

    if pd.isna(cap_remaining):
        cap_remaining = 0.0

    cap_status = _get_cap_status(
        float(cap_remaining)
    )

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
        "cap_remaining": float(cap_remaining),
        "cap_status": cap_status,
        "fines_df": fines_df,
        "totals_by_season": totals_by_season,
    }