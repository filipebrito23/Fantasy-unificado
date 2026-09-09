from __future__ import annotations

import pandas as pd
from sqlalchemy import text

from app_lib.db_v5 import engine


def _read(sql: str, params: dict | None = None) -> pd.DataFrame:
    with engine.connect() as conn:
        return pd.read_sql(text(sql), conn, params=params or {})


def get_available_rounds() -> list[int]:
    df = _read(
        """
        SELECT DISTINCT round
        FROM fantasy_player_game_ratings
        ORDER BY round DESC
        """
    )
    return [int(value) for value in df["round"].dropna().tolist()]


def get_player_season_ranking() -> pd.DataFrame:
    return _read(
        """
        SELECT
            pgr.source_player_id,
            COALESCE(fp.player_name, 'Jogador #' || pgr.source_player_id::TEXT) AS jogador,
            COALESCE(t.team_name, 'Time #' || pgr.team_id::TEXT) AS time,
            COUNT(*) AS jogos,
            ROUND(AVG(pgr.rating)::NUMERIC, 2) AS rating_medio,
            ROUND(AVG(pgr.efficiency)::NUMERIC, 2) AS eficiencia_media,
            ROUND(MAX(pgr.rating)::NUMERIC, 2) AS melhor_rating
        FROM fantasy_player_game_ratings pgr
        LEFT JOIN fantasy_players fp
            ON fp.source_player_id = pgr.source_player_id
        LEFT JOIN teams t
            ON t.team_id = pgr.team_id
        GROUP BY pgr.source_player_id, fp.player_name, pgr.team_id, t.team_name
        ORDER BY rating_medio DESC, eficiencia_media DESC, jogador ASC
        """
    )


def get_player_ratings_by_round(round_number: int | None = None) -> pd.DataFrame:
    params: dict = {}
    where_clause = ""
    if round_number is not None:
        where_clause = "WHERE pgr.round = :round_number"
        params["round_number"] = round_number

    return _read(
        f"""
        SELECT
            pgr.round AS rodada,
            COALESCE(fp.player_name, 'Jogador #' || pgr.source_player_id::TEXT) AS jogador,
            COALESCE(t.team_name, 'Time #' || pgr.team_id::TEXT) AS time,
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
        ORDER BY pgr.round DESC, pgr.rating DESC, pgr.efficiency DESC, jogador ASC
        """,
        params,
    )


def get_player_rating_history(source_player_id: int) -> pd.DataFrame:
    return _read(
        """
        SELECT
            round AS rodada,
            rating,
            efficiency AS eficiencia
        FROM fantasy_player_game_ratings
        WHERE source_player_id = :source_player_id
        ORDER BY round
        """,
        {"source_player_id": source_player_id},
    )


def get_player_options() -> pd.DataFrame:
    return _read(
        """
        SELECT DISTINCT
            pgr.source_player_id,
            COALESCE(fp.player_name, 'Jogador #' || pgr.source_player_id::TEXT) AS jogador
        FROM fantasy_player_game_ratings pgr
        LEFT JOIN fantasy_players fp
            ON fp.source_player_id = pgr.source_player_id
        ORDER BY jogador
        """
    )


def get_team_season_ranking() -> pd.DataFrame:
    return _read(
        """
        SELECT
            tgr.team_id,
            COALESCE(t.team_name, 'Time #' || tgr.team_id::TEXT) AS time,
            COUNT(*) AS jogos,
            ROUND(AVG(tgr.rating)::NUMERIC, 2) AS rating_medio,
            ROUND(AVG(tgr.team_efficiency)::NUMERIC, 2) AS eficiencia_media,
            ROUND(MAX(tgr.rating)::NUMERIC, 2) AS melhor_rating
        FROM fantasy_team_game_ratings tgr
        LEFT JOIN teams t
            ON t.team_id = tgr.team_id
        GROUP BY tgr.team_id, t.team_name
        ORDER BY rating_medio DESC, eficiencia_media DESC, time ASC
        """
    )


def get_team_ratings_by_round(round_number: int | None = None) -> pd.DataFrame:
    params: dict = {}
    where_clause = ""
    if round_number is not None:
        where_clause = "WHERE tgr.round = :round_number"
        params["round_number"] = round_number

    return _read(
        f"""
        SELECT
            tgr.round AS rodada,
            COALESCE(t.team_name, 'Time #' || tgr.team_id::TEXT) AS time,
            tgr.rating,
            tgr.team_efficiency AS eficiencia_time,
            tgr.round_average_efficiency AS media_liga
        FROM fantasy_team_game_ratings tgr
        LEFT JOIN teams t
            ON t.team_id = tgr.team_id
        {where_clause}
        ORDER BY tgr.round DESC, tgr.rating DESC, time ASC
        """,
        params,
    )


def get_team_rating_history(team_id: int) -> pd.DataFrame:
    return _read(
        """
        SELECT
            round AS rodada,
            rating,
            team_efficiency AS eficiencia_time
        FROM fantasy_team_game_ratings
        WHERE team_id = :team_id
        ORDER BY round
        """,
        {"team_id": team_id},
    )


def get_team_options() -> pd.DataFrame:
    return _read(
        """
        SELECT DISTINCT
            tgr.team_id,
            COALESCE(t.team_name, 'Time #' || tgr.team_id::TEXT) AS time
        FROM fantasy_team_game_ratings tgr
        LEFT JOIN teams t
            ON t.team_id = tgr.team_id
        ORDER BY time
        """
    )


def get_round_mvps() -> pd.DataFrame:
    return _read(
        """
        SELECT
            mvp.round AS rodada,
            COALESCE(fp.player_name, 'Jogador #' || mvp.source_player_id::TEXT) AS jogador,
            COALESCE(t.team_name, 'Time #' || mvp.team_id::TEXT) AS time,
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
        ORDER BY mvp.round DESC
        """
    )