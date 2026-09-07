-- Feature 2 - Estatisticas avancadas
-- Queries de exemplo para calculo de metricas

-- ============================================================================
-- 1. Eficiencia por jogador (por jogo)
-- Formula: 1.5*PTS + 3.5*REB + 4.0*AST + 5.0*STL + 5.0*BLK + 3.5*3PT - 3.5*TO
-- ============================================================================

SELECT
    fgs.fantasy_game_stat_id,
    fgs.source_player_id,
    fgs.team_id,
    fg.round,
    fgs.pts,
    fgs.reb,
    fgs.ast,
    fgs.stl,
    fgs.blk,
    fgs.three_pt,
    fgs.turnovers,
    (
        1.5 * fgs.pts
        + 3.5 * fgs.reb
        + 4.0 * fgs.ast
        + 5.0 * fgs.stl
        + 5.0 * fgs.blk
        + 3.5 * fgs.three_pt
        - 3.5 * fgs.turnovers
    ) AS eficiencia
FROM fantasy_game_stats fgs
JOIN fantasy_games fg ON fgs.fantasy_game_id = fg.fantasy_game_id
ORDER BY fg.round, fgs.source_player_id;


-- ============================================================================
-- 2. Media de categoria por time (por rodada)
-- ============================================================================

SELECT
    fg.round,
    fgs.team_id,
    AVG(fgs.pts) AS media_pts,
    AVG(fgs.reb) AS media_reb,
    AVG(fgs.ast) AS media_ast,
    AVG(fgs.stl) AS media_stl,
    AVG(fgs.blk) AS media_blk,
    AVG(fgs.three_pt) AS media_three_pt,
    AVG(fgs.turnovers) AS media_turnovers
FROM fantasy_game_stats fgs
JOIN fantasy_games fg ON fgs.fantasy_game_id = fg.fantasy_game_id
GROUP BY fg.round, fgs.team_id
ORDER BY fg.round, fgs.team_id;


-- ============================================================================
-- 3. Desvio padrao de categoria por time (temporada)
-- ============================================================================

SELECT
    fgs.team_id,
    STDDEV_POP(fgs.pts) AS stddev_pts,
    STDDEV_POP(fgs.reb) AS stddev_reb,
    STDDEV_POP(fgs.ast) AS stddev_ast,
    STDDEV_POP(fgs.stl) AS stddev_stl,
    STDDEV_POP(fgs.blk) AS stddev_blk,
    STDDEV_POP(fgs.three_pt) AS stddev_three_pt,
    STDDEV_POP(fgs.turnovers) AS stddev_turnovers
FROM fantasy_game_stats fgs
GROUP BY fgs.team_id
ORDER BY fgs.team_id;


-- ============================================================================
-- 4. Saldo de categoria por time (PF - PA)
-- Requer que fantasy_games tenha team_1_id e team_2_id
-- ============================================================================

WITH team_stats AS (
    SELECT
        fg.fantasy_game_id,
        fg.team_1_id,
        fg.team_2_id,
        SUM(CASE WHEN fgs.team_id = fg.team_1_id THEN fgs.pts ELSE 0 END) AS team_1_pts,
        SUM(CASE WHEN fgs.team_id = fg.team_2_id THEN fgs.pts ELSE 0 END) AS team_2_pts,
        SUM(CASE WHEN fgs.team_id = fg.team_1_id THEN fgs.reb ELSE 0 END) AS team_1_reb,
        SUM(CASE WHEN fgs.team_id = fg.team_2_id THEN fgs.reb ELSE 0 END) AS team_2_reb,
        SUM(CASE WHEN fgs.team_id = fg.team_1_id THEN fgs.ast ELSE 0 END) AS team_1_ast,
        SUM(CASE WHEN fgs.team_id = fg.team_2_id THEN fgs.ast ELSE 0 END) AS team_2_ast,
        SUM(CASE WHEN fgs.team_id = fg.team_1_id THEN fgs.stl ELSE 0 END) AS team_1_stl,
        SUM(CASE WHEN fgs.team_id = fg.team_2_id THEN fgs.stl ELSE 0 END) AS team_2_stl,
        SUM(CASE WHEN fgs.team_id = fg.team_1_id THEN fgs.blk ELSE 0 END) AS team_1_blk,
        SUM(CASE WHEN fgs.team_id = fg.team_2_id THEN fgs.blk ELSE 0 END) AS team_2_blk,
        SUM(CASE WHEN fgs.team_id = fg.team_1_id THEN fgs.three_pt ELSE 0 END) AS team_1_three_pt,
        SUM(CASE WHEN fgs.team_id = fg.team_2_id THEN fgs.three_pt ELSE 0 END) AS team_2_three_pt,
        SUM(CASE WHEN fgs.team_id = fg.team_1_id THEN fgs.turnovers ELSE 0 END) AS team_1_turnovers,
        SUM(CASE WHEN fgs.team_id = fg.team_2_id THEN fgs.turnovers ELSE 0 END) AS team_2_turnovers
    FROM fantasy_games fg
    JOIN fantasy_game_stats fgs ON fgs.fantasy_game_id = fg.fantasy_game_id
    GROUP BY fg.fantasy_game_id, fg.team_1_id, fg.team_2_id
)
SELECT
    team_1_id AS team_id,
    SUM(team_1_pts) - SUM(team_2_pts) AS saldo_pts,
    SUM(team_1_reb) - SUM(team_2_reb) AS saldo_reb,
    SUM(team_1_ast) - SUM(team_2_ast) AS saldo_ast,
    SUM(team_1_stl) - SUM(team_2_stl) AS saldo_stl,
    SUM(team_1_blk) - SUM(team_2_blk) AS saldo_blk,
    SUM(team_1_three_pt) - SUM(team_2_three_pt) AS saldo_three_pt,
    SUM(team_2_turnovers) - SUM(team_1_turnovers) AS saldo_turnovers
FROM team_stats
GROUP BY team_1_id

UNION ALL

SELECT
    team_2_id AS team_id,
    SUM(team_2_pts) - SUM(team_1_pts) AS saldo_pts,
    SUM(team_2_reb) - SUM(team_1_reb) AS saldo_reb,
    SUM(team_2_ast) - SUM(team_1_ast) AS saldo_ast,
    SUM(team_2_stl) - SUM(team_1_stl) AS saldo_stl,
    SUM(team_2_blk) - SUM(team_1_blk) AS saldo_blk,
    SUM(team_2_three_pt) - SUM(team_1_three_pt) AS saldo_three_pt,
    SUM(team_1_turnovers) - SUM(team_2_turnovers) AS saldo_turnovers
FROM team_stats
GROUP BY team_2_id
ORDER BY team_id;


-- ============================================================================
-- 5. Eficiencia acumulada por jogador (temporada)
-- ============================================================================

SELECT
    fgs.source_player_id,
    SUM(
        1.5 * fgs.pts
        + 3.5 * fgs.reb
        + 4.0 * fgs.ast
        + 5.0 * fgs.stl
        + 5.0 * fgs.blk
        + 3.5 * fgs.three_pt
        - 3.5 * fgs.turnovers
    ) AS eficiencia_acumulada,
    COUNT(*) AS jogos_disputados,
    AVG(
        1.5 * fgs.pts
        + 3.5 * fgs.reb
        + 4.0 * fgs.ast
        + 5.0 * fgs.stl
        + 5.0 * fgs.blk
        + 3.5 * fgs.three_pt
        - 3.5 * fgs.turnovers
    ) AS eficiencia_media
FROM fantasy_game_stats fgs
GROUP BY fgs.source_player_id
ORDER BY eficiencia_acumulada DESC;


-- ============================================================================
-- 6. Eficiencia por milhao de cap
-- Requer salario em fantasy_roster ou fantasy_development
-- ============================================================================

SELECT
    fgs.source_player_id,
    fp.player_name,
    COALESCE(fr.salarie_26_27, fd.salarie_26_27) AS salario,
    SUM(
        1.5 * fgs.pts
        + 3.5 * fgs.reb
        + 4.0 * fgs.ast
        + 5.0 * fgs.stl
        + 5.0 * fgs.blk
        + 3.5 * fgs.three_pt
        - 3.5 * fgs.turnovers
    ) AS eficiencia_acumulada,
    (
        SUM(
            1.5 * fgs.pts
            + 3.5 * fgs.reb
            + 4.0 * fgs.ast
            + 5.0 * fgs.stl
            + 5.0 * fgs.blk
            + 3.5 * fgs.three_pt
            - 3.5 * fgs.turnovers
        ) / NULLIF(COALESCE(fr.salarie_26_27, fd.salarie_26_27), 0)
    ) * 1000000 AS eficiencia_por_milhao
FROM fantasy_game_stats fgs
JOIN fantasy_players fp ON fgs.source_player_id = fp.source_player_id
LEFT JOIN fantasy_roster fr ON fgs.source_player_id = fr.source_player_id
LEFT JOIN fantasy_development fd ON fgs.source_player_id = fd.source_player_id
GROUP BY fgs.source_player_id, fp.player_name, fr.salarie_26_27, fd.salarie_26_27
ORDER BY eficiencia_por_milhao DESC;


-- ============================================================================
-- 7. Media de pontos (ultimas 4, 8, 12 rodadas) por jogador
-- ============================================================================

WITH jogador_rodadas AS (
    SELECT
        fgs.source_player_id,
        fg.round,
        fgs.pts,
        ROW_NUMBER() OVER (PARTITION BY fgs.source_player_id ORDER BY fg.round DESC) AS rodada_regressiva
    FROM fantasy_game_stats fgs
    JOIN fantasy_games fg ON fgs.fantasy_game_id = fg.fantasy_game_id
)
SELECT
    source_player_id,
    AVG(CASE WHEN rodada_regressiva <= 4 THEN pts END) AS media_pts_ultimas_4,
    AVG(CASE WHEN rodada_regressiva <= 8 THEN pts END) AS media_pts_ultimas_8,
    AVG(CASE WHEN rodada_regressiva <= 12 THEN pts END) AS media_pts_ultimas_12,
    AVG(pts) AS media_pts_temporada
FROM jogador_rodadas
GROUP BY source_player_id
ORDER BY source_player_id;