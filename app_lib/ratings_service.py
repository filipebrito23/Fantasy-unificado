from __future__ import annotations

import pandas as pd
import streamlit as st
from sqlalchemy import text

from app_lib.db_v5 import engine
from app_lib.season_config import ACTIVE_SEASON


def _read(sql: str, params: dict | None = None) -> pd.DataFrame:
    with engine.connect() as conn:
        return pd.read_sql(text(sql), conn, params=params or {})


@st.cache_data(ttl=300, show_spinner=False)
def get_available_rounds(
    season: str = ACTIVE_SEASON,
) -> list[int]:
    df = _read(
        """
        SELECT DISTINCT round
        FROM fantasy_player_game_ratings
        WHERE season = :season
        ORDER BY round DESC
        """,
        {"season": season},
    )
    return [int(value) for value in df["round"].dropna().tolist()]


@st.cache_data(ttl=300, show_spinner=False)
def get_player_season_ranking(
    season: str = ACTIVE_SEASON,
) -> pd.DataFrame:
    return _read(
        """
        SELECT
            COALESCE(
                fp.player_name,
                'Jogador #' || pgr.source_player_id::TEXT
            ) AS jogador,
            COALESCE(
                t.team_name,
                'Time #' || pgr.team_id::TEXT
            ) AS time,
            COUNT(*) AS jogos,
            ROUND(AVG(pgr.rating)::NUMERIC, 2) AS rating_medio,
            ROUND(AVG(pgr.efficiency)::NUMERIC, 2) AS eficiencia_media,
            ROUND(MAX(pgr.rating)::NUMERIC, 2) AS melhor_rating
        FROM fantasy_player_game_ratings pgr
        LEFT JOIN fantasy_players fp
            ON fp.source_player_id = pgr.source_player_id
        LEFT JOIN teams t
            ON t.team_id = pgr.team_id
        WHERE pgr.season = :season
        GROUP BY
            pgr.source_player_id,
            fp.player_name,
            pgr.team_id,
            t.team_name
        ORDER BY rating_medio DESC, eficiencia_media DESC, jogador ASC
        """,
        {"season": season},
    )


@st.cache_data(ttl=300, show_spinner=False)
def get_player_ratings_by_round(
    round_number: int | None = None,
    season: str = ACTIVE_SEASON,
) -> pd.DataFrame:
    params: dict = {"season": season}

    if round_number is not None:
        where_clause = """
            WHERE pgr.season = :season
              AND pgr.round = :round_number
        """
        params["round_number"] = round_number
    else:
        where_clause = "WHERE pgr.season = :season"

    return _read(
        f"""
        SELECT
            pgr.round AS rodada,
            COALESCE(
                fp.player_name,
                'Jogador #' || pgr.source_player_id::TEXT
            ) AS jogador,
            COALESCE(
                t.team_name,
                'Time #' || pgr.team_id::TEXT
            ) AS time,
            pgr.rating,
            pgr.efficiency AS eficiencia,
            fgs.pts AS pts,
            fgs.reb AS reb,
            fgs.ast AS ast,
            fgs.stl AS stl,
            fgs.blk AS blk,
            fgs.three_pt AS three_pt,
            fgs.turnovers AS turnovers
        FROM fantasy_player_game_ratings pgr
        JOIN fantasy_game_stats fgs
            ON fgs.fantasy_game_stat_id = pgr.fantasy_game_stat_id
        LEFT JOIN fantasy_players fp
            ON fp.source_player_id = pgr.source_player_id
        LEFT JOIN teams t
            ON t.team_id = pgr.team_id
        {where_clause}
        ORDER BY
            pgr.round DESC,
            pgr.rating DESC,
            pgr.efficiency DESC,
            jogador ASC
        """,
        params,
    )


@st.cache_data(ttl=300, show_spinner=False)
def get_player_rating_history(
    source_player_id: int,
    season: str = ACTIVE_SEASON,
) -> pd.DataFrame:
    return _read(
        """
        SELECT
            round AS rodada,
            rating,
            efficiency AS eficiencia
        FROM fantasy_player_game_ratings
        WHERE season = :season
          AND source_player_id = :source_player_id
        ORDER BY round
        """,
        {
            "season": season,
            "source_player_id": source_player_id,
        },
    )


@st.cache_data(ttl=300, show_spinner=False)
def get_player_options(
    season: str = ACTIVE_SEASON,
) -> pd.DataFrame:
    return _read(
        """
        SELECT DISTINCT
            pgr.source_player_id,
            COALESCE(
                fp.player_name,
                'Jogador #' || pgr.source_player_id::TEXT
            ) AS jogador
        FROM fantasy_player_game_ratings pgr
        LEFT JOIN fantasy_players fp
            ON fp.source_player_id = pgr.source_player_id
        WHERE pgr.season = :season
        ORDER BY jogador
        """,
        {"season": season},
    )


@st.cache_data(ttl=300, show_spinner=False)
def get_team_season_ranking(
    season: str = ACTIVE_SEASON,
) -> pd.DataFrame:
    return _read(
        """
        SELECT
            COALESCE(
                t.team_name,
                'Time #' || tgr.team_id::TEXT
            ) AS time,
            COUNT(*) AS jogos,
            ROUND(AVG(tgr.rating)::NUMERIC, 2) AS rating_medio,
            ROUND(AVG(tgr.team_efficiency)::NUMERIC, 2) AS eficiencia_media,
            ROUND(MAX(tgr.rating)::NUMERIC, 2) AS melhor_rating
        FROM fantasy_team_game_ratings tgr
        LEFT JOIN teams t
            ON t.team_id = tgr.team_id
        WHERE tgr.season = :season
        GROUP BY tgr.team_id, t.team_name
        ORDER BY rating_medio DESC, eficiencia_media DESC, time ASC
        """,
        {"season": season},
    )


@st.cache_data(ttl=300, show_spinner=False)
def get_team_ratings_by_round(
    round_number: int | None = None,
    season: str = ACTIVE_SEASON,
) -> pd.DataFrame:
    params: dict = {"season": season}

    if round_number is not None:
        where_clause = """
            WHERE tgr.season = :season
              AND tgr.round = :round_number
        """
        params["round_number"] = round_number
    else:
        where_clause = "WHERE tgr.season = :season"

    return _read(
        f"""
        SELECT
            tgr.round AS rodada,
            COALESCE(
                t.team_name,
                'Time #' || tgr.team_id::TEXT
            ) AS time,
            tgr.rating,
            tgr.team_efficiency AS eficiencia_time,
            tgr.round_average_efficiency AS media_liga
        FROM fantasy_team_game_ratings tgr
        LEFT JOIN teams t
            ON t.team_id = tgr.team_id
        {where_clause}
        ORDER BY
            tgr.round DESC,
            tgr.rating DESC,
            time ASC
        """,
        params,
    )


@st.cache_data(ttl=300, show_spinner=False)
def get_team_rating_history(
    team_id: int,
    season: str = ACTIVE_SEASON,
) -> pd.DataFrame:
    return _read(
        """
        SELECT
            round AS rodada,
            rating,
            team_efficiency AS eficiencia_time
        FROM fantasy_team_game_ratings
        WHERE season = :season
          AND team_id = :team_id
        ORDER BY round
        """,
        {
            "season": season,
            "team_id": team_id,
        },
    )


@st.cache_data(ttl=300, show_spinner=False)
def get_team_options(
    season: str = ACTIVE_SEASON,
) -> pd.DataFrame:
    return _read(
        """
        SELECT DISTINCT
            tgr.team_id,
            COALESCE(
                t.team_name,
                'Time #' || tgr.team_id::TEXT
            ) AS time
        FROM fantasy_team_game_ratings tgr
        LEFT JOIN teams t
            ON t.team_id = tgr.team_id
        WHERE tgr.season = :season
        ORDER BY time
        """,
        {"season": season},
    )


@st.cache_data(ttl=300, show_spinner=False)
def get_round_mvps(
    season: str = ACTIVE_SEASON,
) -> pd.DataFrame:
    return _read(
        """
        SELECT
            mvp.round AS rodada,
            COALESCE(
                fp.player_name,
                'Jogador #' || mvp.source_player_id::TEXT
            ) AS jogador,
            COALESCE(
                t.team_name,
                'Time #' || mvp.team_id::TEXT
            ) AS time,
            mvp.rating,
            mvp.efficiency AS eficiencia,
            fgs.pts AS pts,
            fgs.reb AS reb,
            fgs.ast AS ast,
            fgs.stl AS stl,
            fgs.blk AS blk,
            fgs.three_pt AS three_pt,
            fgs.turnovers AS turnovers
        FROM fantasy_round_mvps mvp
        JOIN fantasy_game_stats fgs
            ON fgs.fantasy_game_stat_id = mvp.fantasy_game_stat_id
        LEFT JOIN fantasy_players fp
            ON fp.source_player_id = mvp.source_player_id
        LEFT JOIN teams t
            ON t.team_id = mvp.team_id
        WHERE mvp.season = :season
        ORDER BY mvp.round DESC
        """,
        {"season": season},
    )


@st.cache_data(ttl=300, show_spinner=False)
def get_player_round_leaders(
    round_number: int | None = None,
    season: str = ACTIVE_SEASON,
) -> pd.DataFrame:
    params: dict = {"season": season}

    if round_number is not None:
        where_clause = """
            WHERE pgr.season = :season
              AND pgr.round = :round_number
        """
        params["round_number"] = round_number
    else:
        where_clause = "WHERE pgr.season = :season"

    return _read(
        f"""
        SELECT
            pgr.round AS rodada,
            COALESCE(
                fp.player_name,
                'Jogador #' || pgr.source_player_id::TEXT
            ) AS jogador,
            COALESCE(
                t.team_name,
                'Time #' || pgr.team_id::TEXT
            ) AS time,
            pgr.rating,
            pgr.efficiency AS eficiencia,
            fgs.pts AS pts,
            fgs.reb AS reb,
            fgs.ast AS ast,
            fgs.stl AS stl,
            fgs.blk AS blk,
            fgs.three_pt AS three_pt,
            fgs.turnovers AS turnovers
        FROM fantasy_player_game_ratings pgr
        JOIN fantasy_game_stats fgs
            ON fgs.fantasy_game_stat_id = pgr.fantasy_game_stat_id
        LEFT JOIN fantasy_players fp
            ON fp.source_player_id = pgr.source_player_id
        LEFT JOIN teams t
            ON t.team_id = pgr.team_id
        {where_clause}
        ORDER BY pgr.rating DESC, pgr.efficiency DESC, jogador ASC
        LIMIT 3
        """,
        params,
    )


@st.cache_data(ttl=300, show_spinner=False)
def get_player_round_laggards(
    round_number: int | None = None,
    season: str = ACTIVE_SEASON,
) -> pd.DataFrame:
    params: dict = {"season": season}

    if round_number is not None:
        where_clause = """
            WHERE pgr.season = :season
              AND pgr.round = :round_number
        """
        params["round_number"] = round_number
    else:
        where_clause = "WHERE pgr.season = :season"

    return _read(
        f"""
        SELECT
            pgr.round AS rodada,
            COALESCE(
                fp.player_name,
                'Jogador #' || pgr.source_player_id::TEXT
            ) AS jogador,
            COALESCE(
                t.team_name,
                'Time #' || pgr.team_id::TEXT
            ) AS time,
            pgr.rating,
            pgr.efficiency AS eficiencia,
            fgs.pts AS pts,
            fgs.reb AS reb,
            fgs.ast AS ast,
            fgs.stl AS stl,
            fgs.blk AS blk,
            fgs.three_pt AS three_pt,
            fgs.turnovers AS turnovers
        FROM fantasy_player_game_ratings pgr
        JOIN fantasy_game_stats fgs
            ON fgs.fantasy_game_stat_id = pgr.fantasy_game_stat_id
        LEFT JOIN fantasy_players fp
            ON fp.source_player_id = pgr.source_player_id
        LEFT JOIN teams t
            ON t.team_id = pgr.team_id
        {where_clause}
        ORDER BY pgr.rating ASC, pgr.efficiency ASC, jogador ASC
        LIMIT 3
        """,
        params,
    )


@st.cache_data(ttl=300, show_spinner=False)
def get_team_round_leaders(
    round_number: int | None = None,
    season: str = ACTIVE_SEASON,
) -> pd.DataFrame:
    params: dict = {"season": season}

    if round_number is not None:
        where_clause = """
            WHERE tgr.season = :season
              AND tgr.round = :round_number
        """
        params["round_number"] = round_number
    else:
        where_clause = "WHERE tgr.season = :season"

    return _read(
        f"""
        SELECT
            tgr.round AS rodada,
            COALESCE(
                t.team_name,
                'Time #' || tgr.team_id::TEXT
            ) AS time,
            tgr.rating,
            tgr.team_efficiency AS eficiencia_time,
            tgr.round_average_efficiency AS media_liga
        FROM fantasy_team_game_ratings tgr
        LEFT JOIN teams t
            ON t.team_id = tgr.team_id
        {where_clause}
        ORDER BY tgr.rating DESC, tgr.team_efficiency DESC, time ASC
        LIMIT 3
        """,
        params,
    )


@st.cache_data(ttl=300, show_spinner=False)
def get_team_round_laggards(
    round_number: int | None = None,
    season: str = ACTIVE_SEASON,
) -> pd.DataFrame:
    params: dict = {"season": season}

    if round_number is not None:
        where_clause = """
            WHERE tgr.season = :season
              AND tgr.round = :round_number
        """
        params["round_number"] = round_number
    else:
        where_clause = "WHERE tgr.season = :season"

    return _read(
        f"""
        SELECT
            tgr.round AS rodada,
            COALESCE(
                t.team_name,
                'Time #' || tgr.team_id::TEXT
            ) AS time,
            tgr.rating,
            tgr.team_efficiency AS eficiencia_time,
            tgr.round_average_efficiency AS media_liga
        FROM fantasy_team_game_ratings tgr
        LEFT JOIN teams t
            ON t.team_id = tgr.team_id
        {where_clause}
        ORDER BY tgr.rating ASC, tgr.team_efficiency ASC, time ASC
        LIMIT 3
        """,
        params,
    )


@st.cache_data(ttl=300, show_spinner=False)
def get_round_summary_stats(
    round_number: int | None = None,
    season: str = ACTIVE_SEASON,
) -> pd.DataFrame:
    params: dict = {"season": season}
    where_clause = "WHERE season = :season"

    if round_number is not None:
        where_clause += " AND round = :round_number"
        params["round_number"] = round_number

    return _read(
        f"""
        SELECT
            round AS rodada,
            ROUND(AVG(rating)::NUMERIC, 2) AS rating_medio,
            ROUND(AVG(efficiency)::NUMERIC, 2) AS eficiencia_media,
            ROUND(MAX(rating)::NUMERIC, 2) AS rating_maximo,
            ROUND(MIN(rating)::NUMERIC, 2) AS rating_minimo
        FROM fantasy_player_game_ratings
        {where_clause}
        GROUP BY round
        ORDER BY round
        """,
        params,
    )