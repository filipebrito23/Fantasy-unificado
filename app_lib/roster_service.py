from __future__ import annotations

import pandas as pd
import streamlit as st
from sqlalchemy import text

from app_lib.db_v5 import engine

DB_ROSTER_TYPES = {"MAIN": "main", "DEV": "development"}


def _read_sql(sql: str, params: dict | None = None) -> pd.DataFrame:
    with engine.begin() as conn:
        result = conn.execute(text(sql), params or {})
        return pd.DataFrame(result.fetchall(), columns=result.keys())


def _db_roster_type(roster_type: str) -> str:
    key = str(roster_type).strip().upper()
    if key not in DB_ROSTER_TYPES:
        raise ValueError("roster_type deve ser MAIN ou DEV")
    return DB_ROSTER_TYPES[key]

def get_team_fines(
    team_id: int,
) -> pd.DataFrame:
    query = """
        SELECT
            fantasy_fine_id,
            team_id,
            fine_26_27,
            fine_27_28,
            fine_28_29,
            fine_29_30,
            notes
        FROM fantasy_fines
        WHERE team_id = :team_id
        ORDER BY fantasy_fine_id
    """

    return _read_sql(
        query,
        {
            "team_id": int(team_id),
        },
    )


def _pick_year(season: str) -> int:
    return int(str(season).split("-", 1)[0])


@st.cache_data(ttl=60, show_spinner=False)
def get_team_roster(
    team_id: int,
    season: str,
    roster_type: str = "MAIN",
) -> pd.DataFrame:
    return _read_sql(
        """
        SELECT
            frs.team_id,
            frs.source_player_id,
            frs.season,
            frs.roster_type,
            frs.roster_order,
            frs.salary,
            frs.team_option,
            frs.is_active,
            fp.player_name,
            fp.position,
            t.team_name
        FROM fantasy_roster_seasons frs
        JOIN fantasy_players fp
            ON fp.source_player_id = frs.source_player_id
        JOIN teams t
            ON t.team_id = frs.team_id
        WHERE frs.team_id = :team_id
          AND frs.season = :season
          AND frs.roster_type = :roster_type
          AND frs.is_active = TRUE
        ORDER BY
            frs.roster_order NULLS LAST,
            fp.player_name
        """,
        {
            "team_id": int(team_id),
            "season": season,
            "roster_type": _db_roster_type(
                roster_type
            ),
        },
    )


@st.cache_data(ttl=60, show_spinner=False)
def get_team_roster_totals(team_id: int, season: str, roster_type: str = "MAIN") -> pd.DataFrame:
    db_type = _db_roster_type(roster_type)
    cap_limit = 110_000_000 if db_type == "main" else 14_000_000
    df = _read_sql(
        """
        SELECT COALESCE(SUM(COALESCE(salary, 0)), 0) AS salary_total,
               COUNT(*) AS player_count,
               COUNT(*) FILTER (WHERE team_option = TRUE) AS option_count
        FROM fantasy_roster_seasons
        WHERE team_id = :team_id AND season = :season AND roster_type = :roster_type AND is_active = TRUE
        """,
        {"team_id": int(team_id), "season": season, "roster_type": db_type},
    )
    if not df.empty:
        df["salary_total"] = pd.to_numeric(
            df["salary_total"],
            errors="coerce",
        ).fillna(0.0).astype(float)

        df["cap_limit"] = float(cap_limit)

        df["cap_remaining"] = (
            df["cap_limit"] - df["salary_total"]
        ).astype(float)

    return df


@st.cache_data(ttl=60, show_spinner=False)
def get_team_picks(team_id: int, season: str) -> pd.DataFrame:
    return _read_sql(
        """
        SELECT fp.fantasy_pick_id AS pick_id, fp.source_pick_id,
               fp.original_team_pick_id, fp.round, fp.year,
               fp.current_team_owner_id,
               original_team.team_name AS original_team_name,
               current_team.team_name AS current_team_name
        FROM fantasy_picks fp
        LEFT JOIN teams original_team ON original_team.team_id = fp.original_team_pick_id
        LEFT JOIN teams current_team ON current_team.team_id = fp.current_team_owner_id
        WHERE fp.current_team_owner_id = :team_id
          AND fp.year = :pick_year
        ORDER BY fp.year, fp.round, fp.source_pick_id
        """,
        {"team_id": int(team_id), "pick_year": _pick_year(season)},
    )


@st.cache_data(ttl=60, show_spinner=False)
def get_team_roster_positions(team_id: int, season: str, roster_type: str = "MAIN") -> dict[str, int]:
    df = get_team_roster(team_id, season, roster_type)
    if df.empty or "position" not in df.columns:
        return {}
    return df["position"].fillna("-").astype(str).str.strip().value_counts().to_dict()


def invalidate_roster_cache() -> None:
    get_team_roster.clear()
    get_team_roster_totals.clear()
    get_team_picks.clear()
    get_team_roster_positions.clear()
