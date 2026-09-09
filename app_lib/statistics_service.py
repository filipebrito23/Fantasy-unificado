from __future__ import annotations

import pandas as pd
from sqlalchemy import text

from app_lib.db_v5 import engine

EFFICIENCY_FORMULA_LABEL = (
    "1,5×«PTS + 3,5×«REB + 4,0×«AST + 5,0×«STL + 5,0×«BLK + 3,5×«3PT − 3,5×«TO"
)


def _to_dataframe(result) -> pd.DataFrame:
    return pd.DataFrame(result.fetchall(), columns=result.keys())


def _read_sql(sql: str, params: dict | None = None) -> pd.DataFrame:
    with engine.begin() as conn:
        result = conn.execute(text(sql), params or {})
        return _to_dataframe(result)


def _build_in_filter(values: list[int], prefix: str, params: dict) -> str:
    placeholders = []
    for index, value in enumerate(values):
        key = f"{prefix}_{index}"
        params[key] = value
        placeholders.append(f":{key}")
    return ", ".join(placeholders)


def get_statistics_teams() -> pd.DataFrame:
    return _read_sql(
        """
        SELECT team_id, team_name
        FROM teams
        ORDER BY team_name
        """
    )


def get_player_statistics(team_id: int | None = None) -> pd.DataFrame:
    params: dict = {}
    team_filter = ""
    if team_id is not None:
        team_filter = "WHERE b.team_id = :team_id"
        params["team_id"] = team_id

    return _read_sql(
        f"""
        WITH base AS (
            SELECT
                gs.fantasy_game_stat_id,
                gs.fantasy_game_id,
                gs.source_player_id,
                gs.team_id,
                fg.round,
                gs.pts,
                gs.reb,
                gs.ast,
                gs.stl,
                gs.blk,
                gs.three_pt,
                gs.turnovers,
                COALESCE(
                    gs.efficiency,
                    1.5 * COALESCE(gs.pts, 0)
                    + 3.5 * COALESCE(gs.reb, 0)
                    + 4.0 * COALESCE(gs.ast, 0)
                    + 5.0 * COALESCE(gs.stl, 0)
                    + 5.0 * COALESCE(gs.blk, 0)
                    + 3.5 * COALESCE(gs.three_pt, 0)
                    - 3.5 * COALESCE(gs.turnovers, 0)
                ) AS efficiency,
                ROW_NUMBER() OVER (
                    PARTITION BY gs.source_player_id, gs.team_id
                    ORDER BY fg.round DESC, gs.fantasy_game_id DESC, gs.fantasy_game_stat_id DESC
                ) AS recency_rank
            FROM fantasy_game_stats gs
            JOIN fantasy_games fg ON fg.fantasy_game_id = gs.fantasy_game_id
            WHERE
                COALESCE(gs.pts, 0) <> 0
                OR COALESCE(gs.reb, 0) <> 0
                OR COALESCE(gs.ast, 0) <> 0
                OR COALESCE(gs.stl, 0) <> 0
                OR COALESCE(gs.blk, 0) <> 0
                OR COALESCE(gs.three_pt, 0) <> 0
                OR COALESCE(gs.turnovers, 0) <> 0
        ),
        salary_by_player AS (
            SELECT
                fr.source_player_id,
                fr.team_id,
                MAX(COALESCE(fr.salarie_26_27, 0)) AS current_salary
            FROM fantasy_roster fr
            GROUP BY fr.source_player_id, fr.team_id
        ),
        aggregated AS (
            SELECT
                b.source_player_id,
                b.team_id,
                COUNT(DISTINCT b.fantasy_game_id) AS games_played,
                MIN(b.round) AS first_round,
                MAX(b.round) AS last_round,
                SUM(b.pts) AS total_pts,
                SUM(b.reb) AS total_reb,
                SUM(b.ast) AS total_ast,
                SUM(b.stl) AS total_stl,
                SUM(b.blk) AS total_blk,
                SUM(b.three_pt) AS total_three_pt,
                SUM(b.turnovers) AS total_turnovers,
                SUM(b.efficiency) AS total_efficiency,
                AVG(b.pts) AS avg_pts,
                AVG(b.reb) AS avg_reb,
                AVG(b.ast) AS avg_ast,
                AVG(b.stl) AS avg_stl,
                AVG(b.blk) AS avg_blk,
                AVG(b.three_pt) AS avg_three_pt,
                AVG(b.turnovers) AS avg_turnovers,
                AVG(b.efficiency) AS avg_efficiency,
                AVG(b.pts) FILTER (WHERE b.recency_rank <= 4) AS avg_pts_last_4,
                AVG(b.pts) FILTER (WHERE b.recency_rank <= 8) AS avg_pts_last_8,
                AVG(b.pts) FILTER (WHERE b.recency_rank <= 12) AS avg_pts_last_12,
                AVG(b.efficiency) FILTER (WHERE b.recency_rank <= 4) AS avg_efficiency_last_4,
                AVG(b.efficiency) FILTER (WHERE b.recency_rank <= 8) AS avg_efficiency_last_8,
                AVG(b.efficiency) FILTER (WHERE b.recency_rank <= 12) AS avg_efficiency_last_12
            FROM base b
            {team_filter}
            GROUP BY b.source_player_id, b.team_id
        )
        SELECT
            a.source_player_id,
            fp.player_name,
            a.team_id,
            t.team_name,
            COALESCE(fp.position, '') AS position,
            a.games_played,
            a.first_round,
            a.last_round,
            a.total_pts,
            a.total_reb,
            a.total_ast,
            a.total_stl,
            a.total_blk,
            a.total_three_pt,
            a.total_turnovers,
            ROUND(a.total_efficiency::NUMERIC, 2) AS total_efficiency,
            ROUND(a.avg_pts::NUMERIC, 2) AS avg_pts,
            ROUND(a.avg_reb::NUMERIC, 2) AS avg_reb,
            ROUND(a.avg_ast::NUMERIC, 2) AS avg_ast,
            ROUND(a.avg_stl::NUMERIC, 2) AS avg_stl,
            ROUND(a.avg_blk::NUMERIC, 2) AS avg_blk,
            ROUND(a.avg_three_pt::NUMERIC, 2) AS avg_three_pt,
            ROUND(a.avg_turnovers::NUMERIC, 2) AS avg_turnovers,
            ROUND(a.avg_efficiency::NUMERIC, 2) AS avg_efficiency,
            ROUND(a.avg_pts_last_4::NUMERIC, 2) AS avg_pts_last_4,
            ROUND(a.avg_pts_last_8::NUMERIC, 2) AS avg_pts_last_8,
            ROUND(a.avg_pts_last_12::NUMERIC, 2) AS avg_pts_last_12,
            ROUND(a.avg_efficiency_last_4::NUMERIC, 2) AS avg_efficiency_last_4,
            ROUND(a.avg_efficiency_last_8::NUMERIC, 2) AS avg_efficiency_last_8,
            ROUND(a.avg_efficiency_last_12::NUMERIC, 2) AS avg_efficiency_last_12,
            COALESCE(s.current_salary, 0) AS current_salary,
            CASE
                WHEN COALESCE(s.current_salary, 0) > 0
                THEN ROUND(
                    (a.avg_efficiency / s.current_salary * 1000000)::NUMERIC,
                    4
                )
                ELSE NULL
            END AS efficiency_per_million
        FROM aggregated a
        JOIN fantasy_players fp ON fp.source_player_id = a.source_player_id
        JOIN teams t ON t.team_id = a.team_id
        LEFT JOIN salary_by_player s
            ON s.source_player_id = a.source_player_id
            AND s.team_id = a.team_id
        ORDER BY a.avg_efficiency DESC NULLS LAST, a.avg_pts DESC, fp.player_name
        """,
        params,
    )


def get_player_game_log(source_player_id: int, team_id: int) -> pd.DataFrame:
    return _read_sql(
        """
        SELECT
            fg.round,
            gs.fantasy_game_id,
            gs.pts,
            gs.reb,
            gs.ast,
            gs.stl,
            gs.blk,
            gs.three_pt,
            gs.turnovers,
            ROUND(
                COALESCE(
                    gs.efficiency,
                    1.5 * COALESCE(gs.pts, 0)
                    + 3.5 * COALESCE(gs.reb, 0)
                    + 4.0 * COALESCE(gs.ast, 0)
                    + 5.0 * COALESCE(gs.stl, 0)
                    + 5.0 * COALESCE(gs.blk, 0)
                    + 3.5 * COALESCE(gs.three_pt, 0)
                    - 3.5 * COALESCE(gs.turnovers, 0)
                ),
                2
            ) AS efficiency
        FROM fantasy_game_stats gs
        JOIN fantasy_games fg ON fg.fantasy_game_id = gs.fantasy_game_id
        WHERE gs.source_player_id = :source_player_id
          AND gs.team_id = :team_id
        ORDER BY fg.round, gs.fantasy_game_id
        """,
        {"source_player_id": source_player_id, "team_id": team_id},
    )


def get_team_statistics(selected_team_ids: list[int] | None = None) -> pd.DataFrame:
    params: dict = {}
    team_filter = ""
    if selected_team_ids:
        team_filter = (
            f"AND gs.team_id IN ({_build_in_filter(selected_team_ids, 'team', params)})"
        )

    return _read_sql(
        f"""
        WITH per_game AS (
            SELECT
                gs.fantasy_game_id,
                gs.team_id,
                fg.round,
                SUM(COALESCE(gs.pts, 0)) AS pts,
                SUM(COALESCE(gs.reb, 0)) AS reb,
                SUM(COALESCE(gs.ast, 0)) AS ast,
                SUM(COALESCE(gs.stl, 0)) AS stl,
                SUM(COALESCE(gs.blk, 0)) AS blk,
                SUM(COALESCE(gs.three_pt, 0)) AS three_pt,
                SUM(COALESCE(gs.turnovers, 0)) AS turnovers,
                SUM(
                    COALESCE(
                        gs.efficiency,
                        1.5 * COALESCE(gs.pts, 0)
                        + 3.5 * COALESCE(gs.reb, 0)
                        + 4.0 * COALESCE(gs.ast, 0)
                        + 5.0 * COALESCE(gs.stl, 0)
                        + 5.0 * COALESCE(gs.blk, 0)
                        + 3.5 * COALESCE(gs.three_pt, 0)
                        - 3.5 * COALESCE(gs.turnovers, 0)
                    )
                ) AS efficiency
            FROM fantasy_game_stats gs
            JOIN fantasy_games fg ON fg.fantasy_game_id = gs.fantasy_game_id
            WHERE (
                COALESCE(gs.pts, 0) <> 0
                OR COALESCE(gs.reb, 0) <> 0
                OR COALESCE(gs.ast, 0) <> 0
                OR COALESCE(gs.stl, 0) <> 0
                OR COALESCE(gs.blk, 0) <> 0
                OR COALESCE(gs.three_pt, 0) <> 0
                OR COALESCE(gs.turnovers, 0) <> 0
            )
            {team_filter}
            GROUP BY gs.fantasy_game_id, gs.team_id, fg.round
        ),
        game_pairs AS (
            SELECT
                pg.fantasy_game_id,
                pg.team_id,
                pg.round,
                pg.pts,
                pg.reb,
                pg.ast,
                pg.stl,
                pg.blk,
                pg.three_pt,
                pg.turnovers,
                pg.efficiency,
                opp.team_id AS opponent_team_id,
                opp.pts AS opponent_pts,
                opp.reb AS opponent_reb,
                opp.ast AS opponent_ast,
                opp.stl AS opponent_stl,
                opp.blk AS opponent_blk,
                opp.three_pt AS opponent_three_pt,
                opp.turnovers AS opponent_turnovers,
                opp.efficiency AS opponent_efficiency
            FROM per_game pg
            JOIN per_game opp
                ON opp.fantasy_game_id = pg.fantasy_game_id
                AND opp.team_id <> pg.team_id
        ),
        per_game_categories AS (
            SELECT
                gp.*,
                (CASE WHEN gp.pts > gp.opponent_pts THEN 1 ELSE 0 END) AS pts_w,
                (CASE WHEN gp.pts < gp.opponent_pts THEN 1 ELSE 0 END) AS pts_l,
                (CASE WHEN gp.pts = gp.opponent_pts THEN 1 ELSE 0 END) AS pts_t,
                (CASE WHEN gp.reb > gp.opponent_reb THEN 1 ELSE 0 END) AS reb_w,
                (CASE WHEN gp.reb < gp.opponent_reb THEN 1 ELSE 0 END) AS reb_l,
                (CASE WHEN gp.reb = gp.opponent_reb THEN 1 ELSE 0 END) AS reb_t,
                (CASE WHEN gp.ast > gp.opponent_ast THEN 1 ELSE 0 END) AS ast_w,
                (CASE WHEN gp.ast < gp.opponent_ast THEN 1 ELSE 0 END) AS ast_l,
                (CASE WHEN gp.ast = gp.opponent_ast THEN 1 ELSE 0 END) AS ast_t,
                (CASE WHEN gp.stl > gp.opponent_stl THEN 1 ELSE 0 END) AS stl_w,
                (CASE WHEN gp.stl < gp.opponent_stl THEN 1 ELSE 0 END) AS stl_l,
                (CASE WHEN gp.stl = gp.opponent_stl THEN 1 ELSE 0 END) AS stl_t,
                (CASE WHEN gp.blk > gp.opponent_blk THEN 1 ELSE 0 END) AS blk_w,
                (CASE WHEN gp.blk < gp.opponent_blk THEN 1 ELSE 0 END) AS blk_l,
                (CASE WHEN gp.blk = gp.opponent_blk THEN 1 ELSE 0 END) AS blk_t,
                (CASE WHEN gp.three_pt > gp.opponent_three_pt THEN 1 ELSE 0 END) AS three_pt_w,
                (CASE WHEN gp.three_pt < gp.opponent_three_pt THEN 1 ELSE 0 END) AS three_pt_l,
                (CASE WHEN gp.three_pt = gp.opponent_three_pt THEN 1 ELSE 0 END) AS three_pt_t,
                (CASE WHEN gp.turnovers < gp.opponent_turnovers THEN 1 ELSE 0 END) AS to_w,
                (CASE WHEN gp.turnovers > gp.opponent_turnovers THEN 1 ELSE 0 END) AS to_l,
                (CASE WHEN gp.turnovers = gp.opponent_turnovers THEN 1 ELSE 0 END) AS to_t
            FROM game_pairs gp
        ),
        summarized AS (
            SELECT
                team_id,
                COUNT(DISTINCT fantasy_game_id) AS games_with_stats,
                MIN(round) AS first_round,
                MAX(round) AS last_round,
                SUM(pts) AS total_pts,
                SUM(reb) AS total_reb,
                SUM(ast) AS total_ast,
                SUM(stl) AS total_stl,
                SUM(blk) AS total_blk,
                SUM(three_pt) AS total_three_pt,
                SUM(turnovers) AS total_turnovers,
                SUM(efficiency) AS total_efficiency,
                AVG(pts) AS avg_pts,
                AVG(reb) AS avg_reb,
                AVG(ast) AS avg_ast,
                AVG(stl) AS avg_stl,
                AVG(blk) AS avg_blk,
                AVG(three_pt) AS avg_three_pt,
                AVG(turnovers) AS avg_turnovers,
                AVG(efficiency) AS avg_efficiency,
                STDDEV_POP(pts) AS stddev_pts,
                SUM(pts_w) AS pts_wins,
                SUM(pts_l) AS pts_losses,
                SUM(pts_t) AS pts_ties,
                SUM(reb_w) AS reb_wins,
                SUM(reb_l) AS reb_losses,
                SUM(reb_t) AS reb_ties,
                SUM(ast_w) AS ast_wins,
                SUM(ast_l) AS ast_losses,
                SUM(ast_t) AS ast_ties,
                SUM(stl_w) AS stl_wins,
                SUM(stl_l) AS stl_losses,
                SUM(stl_t) AS stl_ties,
                SUM(blk_w) AS blk_wins,
                SUM(blk_l) AS blk_losses,
                SUM(blk_t) AS blk_ties,
                SUM(three_pt_w) AS three_pt_wins,
                SUM(three_pt_l) AS three_pt_losses,
                SUM(three_pt_t) AS three_pt_ties,
                SUM(to_w) AS to_wins,
                SUM(to_l) AS to_losses,
                SUM(to_t) AS to_ties
            FROM per_game_categories
            GROUP BY team_id
        )
        SELECT
            s.team_id,
            t.team_name,
            s.games_with_stats,
            s.first_round,
            s.last_round,
            ROUND(s.total_pts, 2) AS total_pts,
            ROUND(s.total_reb, 2) AS total_reb,
            ROUND(s.total_ast, 2) AS total_ast,
            ROUND(s.total_stl, 2) AS total_stl,
            ROUND(s.total_blk, 2) AS total_blk,
            ROUND(s.total_three_pt, 2) AS total_three_pt,
            ROUND(s.total_turnovers, 2) AS total_turnovers,
            ROUND(s.total_efficiency, 2) AS total_efficiency,
            ROUND(s.avg_pts, 2) AS avg_pts,
            ROUND(s.avg_reb, 2) AS avg_reb,
            ROUND(s.avg_ast, 2) AS avg_ast,
            ROUND(s.avg_stl, 2) AS avg_stl,
            ROUND(s.avg_blk, 2) AS avg_blk,
            ROUND(s.avg_three_pt, 2) AS avg_three_pt,
            ROUND(s.avg_turnovers, 2) AS avg_turnovers,
            ROUND(s.avg_efficiency, 2) AS avg_efficiency,
            ROUND(s.stddev_pts, 2) AS stddev_pts,
            (s.pts_wins + s.reb_wins + s.ast_wins + s.stl_wins + s.blk_wins + s.three_pt_wins + s.to_wins) AS category_wins,
            (s.pts_losses + s.reb_losses + s.ast_losses + s.stl_losses + s.blk_losses + s.three_pt_losses + s.to_losses) AS category_losses,
            (s.pts_ties + s.reb_ties + s.ast_ties + s.stl_ties + s.blk_ties + s.three_pt_ties + s.to_ties) AS category_ties,
            (s.pts_wins + s.reb_wins + s.ast_wins + s.stl_wins + s.blk_wins + s.three_pt_wins + s.to_wins)
                - (s.pts_losses + s.reb_losses + s.ast_losses + s.stl_losses + s.blk_losses + s.three_pt_losses + s.to_losses) AS category_balance,
            s.pts_wins, s.pts_losses, s.pts_ties,
            s.reb_wins, s.reb_losses, s.reb_ties,
            s.ast_wins, s.ast_losses, s.ast_ties,
            s.stl_wins, s.stl_losses, s.stl_ties,
            s.blk_wins, s.blk_losses, s.blk_ties,
            s.three_pt_wins, s.three_pt_losses, s.three_pt_ties,
            s.to_wins, s.to_losses, s.to_ties
        FROM summarized s
        JOIN teams t ON t.team_id = s.team_id
        ORDER BY category_wins DESC, category_balance DESC, avg_efficiency DESC, t.team_name
        """,
        params,
    )


def get_team_game_log(team_id: int) -> pd.DataFrame:
    return _read_sql(
        """
        WITH per_game AS (
            SELECT
                gs.fantasy_game_id,
                gs.team_id,
                fg.round,
                SUM(COALESCE(gs.pts, 0)) AS pts,
                SUM(COALESCE(gs.reb, 0)) AS reb,
                SUM(COALESCE(gs.ast, 0)) AS ast,
                SUM(COALESCE(gs.stl, 0)) AS stl,
                SUM(COALESCE(gs.blk, 0)) AS blk,
                SUM(COALESCE(gs.three_pt, 0)) AS three_pt,
                SUM(COALESCE(gs.turnovers, 0)) AS turnovers,
                SUM(COALESCE(gs.efficiency, 0)) AS efficiency
            FROM fantasy_game_stats gs
            JOIN fantasy_games fg ON fg.fantasy_game_id = gs.fantasy_game_id
            WHERE
                COALESCE(gs.pts, 0) <> 0
                OR COALESCE(gs.reb, 0) <> 0
                OR COALESCE(gs.ast, 0) <> 0
                OR COALESCE(gs.stl, 0) <> 0
                OR COALESCE(gs.blk, 0) <> 0
                OR COALESCE(gs.three_pt, 0) <> 0
                OR COALESCE(gs.turnovers, 0) <> 0
            GROUP BY gs.fantasy_game_id, gs.team_id, fg.round
        ),
        mine_with_opp AS (
            SELECT
                mine.round,
                mine.fantasy_game_id,
                opp.team_id AS opponent_team_id,
                t.team_name AS opponent,
                mine.pts,
                mine.reb,
                mine.ast,
                mine.stl,
                mine.blk,
                mine.three_pt,
                mine.turnovers,
                ROUND(mine.efficiency, 2) AS efficiency,
                (
                    (CASE WHEN mine.pts > opp.pts THEN 1 ELSE 0 END) +
                    (CASE WHEN mine.reb > opp.reb THEN 1 ELSE 0 END) +
                    (CASE WHEN mine.ast > opp.ast THEN 1 ELSE 0 END) +
                    (CASE WHEN mine.stl > opp.stl THEN 1 ELSE 0 END) +
                    (CASE WHEN mine.blk > opp.blk THEN 1 ELSE 0 END) +
                    (CASE WHEN mine.three_pt > opp.three_pt THEN 1 ELSE 0 END) +
                    (CASE WHEN mine.turnovers < opp.turnovers THEN 1 ELSE 0 END)
                ) AS category_wins,
                (
                    (CASE WHEN mine.pts < opp.pts THEN 1 ELSE 0 END) +
                    (CASE WHEN mine.reb < opp.reb THEN 1 ELSE 0 END) +
                    (CASE WHEN mine.ast < opp.ast THEN 1 ELSE 0 END) +
                    (CASE WHEN mine.stl < opp.stl THEN 1 ELSE 0 END) +
                    (CASE WHEN mine.blk < opp.blk THEN 1 ELSE 0 END) +
                    (CASE WHEN mine.three_pt < opp.three_pt THEN 1 ELSE 0 END) +
                    (CASE WHEN mine.turnovers > opp.turnovers THEN 1 ELSE 0 END)
                ) AS category_losses
            FROM per_game mine
            JOIN per_game opp
                ON opp.fantasy_game_id = mine.fantasy_game_id
                AND opp.team_id <> mine.team_id
            JOIN teams t ON t.team_id = opp.team_id
            WHERE mine.team_id = :team_id
        )
        SELECT *
        FROM mine_with_opp
        ORDER BY round, fantasy_game_id
        """,
        {"team_id": team_id},
    )


# =========================
# Feature 2 ev1 – Consistency
# =========================


def get_player_consistency(team_id: int | None = None, min_games: int = 2) -> pd.DataFrame:
    """
    Média e desvio-padrã««o (amostral) por jogador para:
    PTS, REB, AST, STL, BLK, 3PT, TO e eficiência.
    """
    params: dict = {"min_games": min_games}
    team_filter = ""
    if team_id is not None:
        team_filter = "AND b.team_id = :team_id"
        params["team_id"] = team_id

    return _read_sql(
        f"""
        WITH base AS (
            SELECT
                gs.source_player_id,
                gs.team_id,
                gs.pts,
                gs.reb,
                gs.ast,
                gs.stl,
                gs.blk,
                gs.three_pt,
                gs.turnovers,
                COALESCE(
                    gs.efficiency,
                    1.5 * COALESCE(gs.pts, 0)
                    + 3.5 * COALESCE(gs.reb, 0)
                    + 4.0 * COALESCE(gs.ast, 0)
                    + 5.0 * COALESCE(gs.stl, 0)
                    + 5.0 * COALESCE(gs.blk, 0)
                    + 3.5 * COALESCE(gs.three_pt, 0)
                    - 3.5 * COALESCE(gs.turnovers, 0)
                ) AS efficiency
            FROM fantasy_game_stats gs
            JOIN fantasy_games fg ON fg.fantasy_game_id = gs.fantasy_game_id
            WHERE
                (
                    COALESCE(gs.pts, 0) <> 0
                    OR COALESCE(gs.reb, 0) <> 0
                    OR COALESCE(gs.ast, 0) <> 0
                    OR COALESCE(gs.stl, 0) <> 0
                    OR COALESCE(gs.blk, 0) <> 0
                    OR COALESCE(gs.three_pt, 0) <> 0
                    OR COALESCE(gs.turnovers, 0) <> 0
                )
                {team_filter}
        ),
        aggregated AS (
            SELECT
                source_player_id,
                team_id,
                COUNT(*) AS games_played,
                AVG(pts) AS avg_pts,
                AVG(reb) AS avg_reb,
                AVG(ast) AS avg_ast,
                AVG(stl) AS avg_stl,
                AVG(blk) AS avg_blk,
                AVG(three_pt) AS avg_three_pt,
                AVG(turnovers) AS avg_turnovers,
                AVG(efficiency) AS avg_efficiency,
                STDDEV_SAMP(pts) AS stddev_pts,
                STDDEV_SAMP(reb) AS stddev_reb,
                STDDEV_SAMP(ast) AS stddev_ast,
                STDDEV_SAMP(stl) AS stddev_stl,
                STDDEV_SAMP(blk) AS stddev_blk,
                STDDEV_SAMP(three_pt) AS stddev_three_pt,
                STDDEV_SAMP(turnovers) AS stddev_turnovers,
                STDDEV_SAMP(efficiency) AS stddev_efficiency
            FROM base
            GROUP BY source_player_id, team_id
            HAVING COUNT(*) >= :min_games
        )
        SELECT
            a.source_player_id,
            fp.player_name,
            a.team_id,
            t.team_name,
            a.games_played,
            ROUND(a.avg_pts::NUMERIC, 2) AS avg_pts,
            ROUND(a.avg_reb::NUMERIC, 2) AS avg_reb,
            ROUND(a.avg_ast::NUMERIC, 2) AS avg_ast,
            ROUND(a.avg_stl::NUMERIC, 2) AS avg_stl,
            ROUND(a.avg_blk::NUMERIC, 2) AS avg_blk,
            ROUND(a.avg_three_pt::NUMERIC, 2) AS avg_three_pt,
            ROUND(a.avg_turnovers::NUMERIC, 2) AS avg_turnovers,
            ROUND(a.avg_efficiency::NUMERIC, 2) AS avg_efficiency,
            ROUND(a.stddev_pts::NUMERIC, 2) AS stddev_pts,
            ROUND(a.stddev_reb::NUMERIC, 2) AS stddev_reb,
            ROUND(a.stddev_ast::NUMERIC, 2) AS stddev_ast,
            ROUND(a.stddev_stl::NUMERIC, 2) AS stddev_stl,
            ROUND(a.stddev_blk::NUMERIC, 2) AS stddev_blk,
            ROUND(a.stddev_three_pt::NUMERIC, 2) AS stddev_three_pt,
            ROUND(a.stddev_turnovers::NUMERIC, 2) AS stddev_turnovers,
            ROUND(a.stddev_efficiency::NUMERIC, 2) AS stddev_efficiency
        FROM aggregated a
        JOIN fantasy_players fp ON fp.source_player_id = a.source_player_id
        JOIN teams t ON t.team_id = a.team_id
        ORDER BY a.avg_efficiency DESC, a.avg_pts DESC, fp.player_name
        """,
        params,
    )


def get_team_consistency(selected_team_ids: list[int] | None = None, min_games: int = 2) -> pd.DataFrame:
    """
    Média e desvio-padrã««o (amostral) por time para:
    PTS, REB, AST, STL, BLK, 3PT, TO e eficiência.
    """
    params: dict = {"min_games": min_games}
    team_filter = ""
    if selected_team_ids:
        team_filter = (
            f"AND gs.team_id IN ({_build_in_filter(selected_team_ids, 'team', params)})"
        )

    return _read_sql(
        f"""
        WITH per_game AS (
            SELECT
                gs.team_id,
                SUM(COALESCE(gs.pts, 0)) AS pts,
                SUM(COALESCE(gs.reb, 0)) AS reb,
                SUM(COALESCE(gs.ast, 0)) AS ast,
                SUM(COALESCE(gs.stl, 0)) AS stl,
                SUM(COALESCE(gs.blk, 0)) AS blk,
                SUM(COALESCE(gs.three_pt, 0)) AS three_pt,
                SUM(COALESCE(gs.turnovers, 0)) AS turnovers,
                SUM(
                    COALESCE(
                        gs.efficiency,
                        1.5 * COALESCE(gs.pts, 0)
                        + 3.5 * COALESCE(gs.reb, 0)
                        + 4.0 * COALESCE(gs.ast, 0)
                        + 5.0 * COALESCE(gs.stl, 0)
                        + 5.0 * COALESCE(gs.blk, 0)
                        + 3.5 * COALESCE(gs.three_pt, 0)
                        - 3.5 * COALESCE(gs.turnovers, 0)
                    )
                ) AS efficiency
            FROM fantasy_game_stats gs
            JOIN fantasy_games fg ON fg.fantasy_game_id = gs.fantasy_game_id
            WHERE
                (
                    COALESCE(gs.pts, 0) <> 0
                    OR COALESCE(gs.reb, 0) <> 0
                    OR COALESCE(gs.ast, 0) <> 0
                    OR COALESCE(gs.stl, 0) <> 0
                    OR COALESCE(gs.blk, 0) <> 0
                    OR COALESCE(gs.three_pt, 0) <> 0
                    OR COALESCE(gs.turnovers, 0) <> 0
                )
                {team_filter}
            GROUP BY gs.fantasy_game_id, gs.team_id
        ),
        aggregated AS (
            SELECT
                team_id,
                COUNT(*) AS games_with_stats,
                AVG(pts) AS avg_pts,
                AVG(reb) AS avg_reb,
                AVG(ast) AS avg_ast,
                AVG(stl) AS avg_stl,
                AVG(blk) AS avg_blk,
                AVG(three_pt) AS avg_three_pt,
                AVG(turnovers) AS avg_turnovers,
                AVG(efficiency) AS avg_efficiency,
                STDDEV_SAMP(pts) AS stddev_pts,
                STDDEV_SAMP(reb) AS stddev_reb,
                STDDEV_SAMP(ast) AS stddev_ast,
                STDDEV_SAMP(stl) AS stddev_stl,
                STDDEV_SAMP(blk) AS stddev_blk,
                STDDEV_SAMP(three_pt) AS stddev_three_pt,
                STDDEV_SAMP(turnovers) AS stddev_turnovers,
                STDDEV_SAMP(efficiency) AS stddev_efficiency
            FROM per_game
            GROUP BY team_id
            HAVING COUNT(*) >= :min_games
        )
        SELECT
            a.team_id,
            t.team_name,
            a.games_with_stats,
            ROUND(a.avg_pts::NUMERIC, 2) AS avg_pts,
            ROUND(a.avg_reb::NUMERIC, 2) AS avg_reb,
            ROUND(a.avg_ast::NUMERIC, 2) AS avg_ast,
            ROUND(a.avg_stl::NUMERIC, 2) AS avg_stl,
            ROUND(a.avg_blk::NUMERIC, 2) AS avg_blk,
            ROUND(a.avg_three_pt::NUMERIC, 2) AS avg_three_pt,
            ROUND(a.avg_turnovers::NUMERIC, 2) AS avg_turnovers,
            ROUND(a.avg_efficiency::NUMERIC, 2) AS avg_efficiency,
            ROUND(a.stddev_pts::NUMERIC, 2) AS stddev_pts,
            ROUND(a.stddev_reb::NUMERIC, 2) AS stddev_reb,
            ROUND(a.stddev_ast::NUMERIC, 2) AS stddev_ast,
            ROUND(a.stddev_stl::NUMERIC, 2) AS stddev_stl,
            ROUND(a.stddev_blk::NUMERIC, 2) AS stddev_blk,
            ROUND(a.stddev_three_pt::NUMERIC, 2) AS stddev_three_pt,
            ROUND(a.stddev_turnovers::NUMERIC, 2) AS stddev_turnovers,
            ROUND(a.stddev_efficiency::NUMERIC, 2) AS stddev_efficiency
        FROM aggregated a
        JOIN teams t ON t.team_id = a.team_id
        ORDER BY a.avg_efficiency DESC, a.avg_pts DESC, t.team_name
        """,
        params,
    )


def get_player_consistency_history(
    source_player_id: int,
    team_id: int,
    metric: str = "pts",
) -> pd.DataFrame:
    """
    Histórico por rodada para um jogador, com:
    - valor da métrica
    - média acumulada até a rodada
    - desvio-padrã««o acumulado (amostral)
    - limites inferior e superior (mÃ©dia ± 1 DP)
    """
    allowed = {
        "pts",
        "reb",
        "ast",
        "stl",
        "blk",
        "three_pt",
        "turnovers",
        "efficiency",
    }
    if metric not in allowed:
        raise ValueError(f"metric must be one of {allowed}")

    return _read_sql(
        f"""
        WITH ordered AS (
            SELECT
                fg.round,
                gs.fantasy_game_id,
                gs.pts,
                gs.reb,
                gs.ast,
                gs.stl,
                gs.blk,
                gs.three_pt,
                gs.turnovers,
                COALESCE(
                    gs.efficiency,
                    1.5 * COALESCE(gs.pts, 0)
                    + 3.5 * COALESCE(gs.reb, 0)
                    + 4.0 * COALESCE(gs.ast, 0)
                    + 5.0 * COALESCE(gs.stl, 0)
                    + 5.0 * COALESCE(gs.blk, 0)
                    + 3.5 * COALESCE(gs.three_pt, 0)
                    - 3.5 * COALESCE(gs.turnovers, 0)
                ) AS efficiency
            FROM fantasy_game_stats gs
            JOIN fantasy_games fg ON fg.fantasy_game_id = gs.fantasy_game_id
            WHERE gs.source_player_id = :source_player_id
              AND gs.team_id = :team_id
            ORDER BY fg.round, gs.fantasy_game_id
        ),
        with_stats AS (
            SELECT
                round,
                {metric} AS value,
                AVG({metric}) OVER (
                    ORDER BY round, fantasy_game_id
                    ROWS BETWEEN UNBOUNDED PRECEDING AND CURRENT ROW
                ) AS running_avg,
                STDDEV_SAMP({metric}) OVER (
                    ORDER BY round, fantasy_game_id
                    ROWS BETWEEN UNBOUNDED PRECEDING AND CURRENT ROW
                ) AS running_stddev
            FROM ordered
        )
        SELECT
            round,
            ROUND(value::NUMERIC, 2) AS value,
            ROUND(running_avg::NUMERIC, 2) AS running_avg,
            COALESCE(ROUND(running_stddev::NUMERIC, 2), 0) AS running_stddev,
            ROUND((running_avg - COALESCE(running_stddev, 0))::NUMERIC, 2) AS lower_bound,
            ROUND((running_avg + COALESCE(running_stddev, 0))::NUMERIC, 2) AS upper_bound
        FROM with_stats
        ORDER BY round, fantasy_game_id
        """,
        {"source_player_id": source_player_id, "team_id": team_id, "metric": metric},
    )


def get_team_consistency_history(
    team_id: int,
    metric: str = "pts",
) -> pd.DataFrame:
    """
    Histórico por rodada para um time, com:
    - valor da métrica
    - média acumulada até a rodada
    - desvio-padrão acumulado (amostral)
    - limites inferior e superior (média ± 1 DP)
    """
    allowed = {
        "pts",
        "reb",
        "ast",
        "stl",
        "blk",
        "three_pt",
        "turnovers",
        "efficiency",
    }
    if metric not in allowed:
        raise ValueError(f"metric must be one of {allowed}")

    return _read_sql(
        f"""
        WITH per_game AS (
            SELECT
                fg.round,
                gs.fantasy_game_id,
                gs.team_id,
                SUM(COALESCE(gs.pts, 0)) AS pts,
                SUM(COALESCE(gs.reb, 0)) AS reb,
                SUM(COALESCE(gs.ast, 0)) AS ast,
                SUM(COALESCE(gs.stl, 0)) AS stl,
                SUM(COALESCE(gs.blk, 0)) AS blk,
                SUM(COALESCE(gs.three_pt, 0)) AS three_pt,
                SUM(COALESCE(gs.turnovers, 0)) AS turnovers,
                SUM(
                    COALESCE(
                        gs.efficiency,
                        1.5 * COALESCE(gs.pts, 0)
                        + 3.5 * COALESCE(gs.reb, 0)
                        + 4.0 * COALESCE(gs.ast, 0)
                        + 5.0 * COALESCE(gs.stl, 0)
                        + 5.0 * COALESCE(gs.blk, 0)
                        + 3.5 * COALESCE(gs.three_pt, 0)
                        - 3.5 * COALESCE(gs.turnovers, 0)
                    )
                ) AS efficiency
            FROM fantasy_game_stats gs
            JOIN fantasy_games fg ON fg.fantasy_game_id = gs.fantasy_game_id
            WHERE
                (
                    COALESCE(gs.pts, 0) <> 0
                    OR COALESCE(gs.reb, 0) <> 0
                    OR COALESCE(gs.ast, 0) <> 0
                    OR COALESCE(gs.stl, 0) <> 0
                    OR COALESCE(gs.blk, 0) <> 0
                    OR COALESCE(gs.three_pt, 0) <> 0
                    OR COALESCE(gs.turnovers, 0) <> 0
                )
            GROUP BY gs.fantasy_game_id, gs.team_id, fg.round
        ),
        with_stats AS (
            SELECT
                round,
                fantasy_game_id,
                {metric} AS value,
                AVG({metric}) OVER (
                    ORDER BY round, fantasy_game_id
                    ROWS BETWEEN UNBOUNDED PRECEDING AND CURRENT ROW
                ) AS running_avg,
                STDDEV_SAMP({metric}) OVER (
                    ORDER BY round, fantasy_game_id
                    ROWS BETWEEN UNBOUNDED PRECEDING AND CURRENT ROW
                ) AS running_stddev
            FROM per_game
            WHERE team_id = :team_id
        )
        SELECT
            round,
            ROUND(value::NUMERIC, 2) AS value,
            ROUND(running_avg::NUMERIC, 2) AS running_avg,
            COALESCE(ROUND(running_stddev::NUMERIC, 2), 0) AS running_stddev,
            ROUND((running_avg - COALESCE(running_stddev, 0))::NUMERIC, 2) AS lower_bound,
            ROUND((running_avg + COALESCE(running_stddev, 0))::NUMERIC, 2) AS upper_bound
        FROM with_stats
        ORDER BY round, fantasy_game_id
        """,
        {"team_id": team_id, "metric": metric},
    )


def get_player_consistency_scatter(
    team_id: int | None = None,
    min_games: int = 4,
    metric: str = "efficiency",
) -> pd.DataFrame:
    """
    Dispersão média × desvio-padrão para jogadores.
    """
    allowed = {
        "pts",
        "reb",
        "ast",
        "stl",
        "blk",
        "three_pt",
        "turnovers",
        "efficiency",
    }
    if metric not in allowed:
        raise ValueError(f"metric must be one of {allowed}")

    params: dict = {"min_games": min_games}
    team_filter = ""
    if team_id is not None:
        team_filter = "AND b.team_id = :team_id"
        params["team_id"] = team_id

    # Calcular a métrica corretamente
    metric_expr = f"""
        COALESCE(
            gs.efficiency,
            1.5 * COALESCE(gs.pts, 0)
            + 3.5 * COALESCE(gs.reb, 0)
            + 4.0 * COALESCE(gs.ast, 0)
            + 5.0 * COALESCE(gs.stl, 0)
            + 5.0 * COALESCE(gs.blk, 0)
            + 3.5 * COALESCE(gs.three_pt, 0)
            - 3.5 * COALESCE(gs.turnovers, 0)
        )""" if metric == "efficiency" else f"COALESCE(gs.{metric}, 0)"

    return _read_sql(
        f"""
        WITH base AS (
            SELECT
                gs.source_player_id,
                gs.team_id,
                {metric_expr} AS value
            FROM fantasy_game_stats gs
            JOIN fantasy_games fg ON fg.fantasy_game_id = gs.fantasy_game_id
            WHERE
                (
                    COALESCE(gs.pts, 0) <> 0
                    OR COALESCE(gs.reb, 0) <> 0
                    OR COALESCE(gs.ast, 0) <> 0
                    OR COALESCE(gs.stl, 0) <> 0
                    OR COALESCE(gs.blk, 0) <> 0
                    OR COALESCE(gs.three_pt, 0) <> 0
                    OR COALESCE(gs.turnovers, 0) <> 0
                )
                {team_filter}
        ),
        aggregated AS (
            SELECT
                source_player_id,
                team_id,
                COUNT(*) AS games_played,
                AVG(value) AS avg_value,
                STDDEV_SAMP(value) AS stddev_value
            FROM base
            GROUP BY source_player_id, team_id
            HAVING COUNT(*) >= :min_games
        )
        SELECT
            a.source_player_id,
            fp.player_name,
            a.team_id,
            t.team_name,
            a.games_played,
            ROUND(a.avg_value::NUMERIC, 2) AS avg_value,
            COALESCE(ROUND(a.stddev_value::NUMERIC, 2), 0) AS stddev_value
        FROM aggregated a
        JOIN fantasy_players fp ON fp.source_player_id = a.source_player_id
        JOIN teams t ON t.team_id = a.team_id
        ORDER BY a.avg_value DESC, fp.player_name
        """,
        params,
    )


def get_team_consistency_scatter(
    selected_team_ids: list[int] | None = None,
    min_games: int = 3,
    metric: str = "efficiency",
) -> pd.DataFrame:
    """
    Dispersão média × desvio-padrão para times.
    """
    allowed = {
        "pts",
        "reb",
        "ast",
        "stl",
        "blk",
        "three_pt",
        "turnovers",
        "efficiency",
    }
    if metric not in allowed:
        raise ValueError(f"metric must be one of {allowed}")

    params: dict = {"min_games": min_games}
    team_filter = ""
    if selected_team_ids:
        team_filter = (
            f"AND gs.team_id IN ({_build_in_filter(selected_team_ids, 'team', params)})"
        )

    metric_expr = f"""
        SUM(
            COALESCE(
                gs.efficiency,
                1.5 * COALESCE(gs.pts, 0)
                + 3.5 * COALESCE(gs.reb, 0)
                + 4.0 * COALESCE(gs.ast, 0)
                + 5.0 * COALESCE(gs.stl, 0)
                + 5.0 * COALESCE(gs.blk, 0)
                + 3.5 * COALESCE(gs.three_pt, 0)
                - 3.5 * COALESCE(gs.turnovers, 0)
            )
        )""" if metric == "efficiency" else f"SUM(COALESCE(gs.{metric}, 0))"

    return _read_sql(
        f"""
        WITH per_game AS (
            SELECT
                gs.fantasy_game_id,
                gs.team_id,
                {metric_expr} AS value
            FROM fantasy_game_stats gs
            JOIN fantasy_games fg ON fg.fantasy_game_id = gs.fantasy_game_id
            WHERE
                (
                    COALESCE(gs.pts, 0) <> 0
                    OR COALESCE(gs.reb, 0) <> 0
                    OR COALESCE(gs.ast, 0) <> 0
                    OR COALESCE(gs.stl, 0) <> 0
                    OR COALESCE(gs.blk, 0) <> 0
                    OR COALESCE(gs.three_pt, 0) <> 0
                    OR COALESCE(gs.turnovers, 0) <> 0
                )
                {team_filter}
            GROUP BY gs.fantasy_game_id, gs.team_id
        ),
        aggregated AS (
            SELECT
                team_id,
                COUNT(*) AS games_with_stats,
                AVG(value) AS avg_value,
                STDDEV_SAMP(value) AS stddev_value
            FROM per_game
            GROUP BY team_id
            HAVING COUNT(*) >= :min_games
        )
        SELECT
            a.team_id,
            t.team_name,
            a.games_with_stats,
            ROUND(a.avg_value::NUMERIC, 2) AS avg_value,
            COALESCE(ROUND(a.stddev_value::NUMERIC, 2), 0) AS stddev_value
        FROM aggregated a
        JOIN teams t ON t.team_id = a.team_id
        ORDER BY a.avg_value DESC, t.team_name
        """,
        params,
    )