-- ============================================================================
-- CORRECAO: Atualizar fantasy_games com nomes completos e criterios vencidos
-- ============================================================================

-- 1. Atualizar team_1_name e team_2_name para nomes completos
UPDATE fantasy_games fg
SET 
    team_1_name = t1.team_name,
    team_2_name = t2.team_name
FROM teams t1, teams t2
WHERE fg.team_1_id = t1.team_id
  AND fg.team_2_id = t2.team_id
  AND (fg.team_1_name != t1.team_name OR fg.team_2_name != t2.team_name);

-- 2. Calcular e atualizar team_1_points e team_2_points como criterios vencidos
-- Para TO, menor valor vence. Para as demais, maior valor vence.
WITH team_stats AS (
    SELECT 
        gs.fantasy_game_id,
        gs.team_id,
        SUM(gs.pts) as total_pts,
        SUM(gs.reb) as total_reb,
        SUM(gs.ast) as total_ast,
        SUM(gs.stl) as total_stl,
        SUM(gs.blk) as total_blk,
        SUM(gs.three_pt) as total_three_pt,
        SUM(gs.turnovers) as total_to
    FROM fantasy_game_stats gs
    GROUP BY gs.fantasy_game_id, gs.team_id
),
game_categories AS (
    SELECT 
        fg.fantasy_game_id,
        fg.team_1_id,
        fg.team_2_id,
        COALESCE(ts1.total_pts, 0) as team_1_pts,
        COALESCE(ts2.total_pts, 0) as team_2_pts,
        COALESCE(ts1.total_reb, 0) as team_1_reb,
        COALESCE(ts2.total_reb, 0) as team_2_reb,
        COALESCE(ts1.total_ast, 0) as team_1_ast,
        COALESCE(ts2.total_ast, 0) as team_2_ast,
        COALESCE(ts1.total_stl, 0) as team_1_stl,
        COALESCE(ts2.total_stl, 0) as team_2_stl,
        COALESCE(ts1.total_blk, 0) as team_1_blk,
        COALESCE(ts2.total_blk, 0) as team_2_blk,
        COALESCE(ts1.total_three_pt, 0) as team_1_three_pt,
        COALESCE(ts2.total_three_pt, 0) as team_2_three_pt,
        COALESCE(ts1.total_to, 0) as team_1_to,
        COALESCE(ts2.total_to, 0) as team_2_to
    FROM fantasy_games fg
    LEFT JOIN team_stats ts1 ON ts1.fantasy_game_id = fg.fantasy_game_id AND ts1.team_id = fg.team_1_id
    LEFT JOIN team_stats ts2 ON ts2.fantasy_game_id = fg.fantasy_game_id AND ts2.team_id = fg.team_2_id
),
category_counts AS (
    SELECT 
        fantasy_game_id,
        team_1_id,
        team_2_id,
        -- Criterios vencidos pelo time 1
        (
            (CASE WHEN team_1_pts > team_2_pts THEN 1 ELSE 0 END) +
            (CASE WHEN team_1_reb > team_2_reb THEN 1 ELSE 0 END) +
            (CASE WHEN team_1_ast > team_2_ast THEN 1 ELSE 0 END) +
            (CASE WHEN team_1_stl > team_2_stl THEN 1 ELSE 0 END) +
            (CASE WHEN team_1_blk > team_2_blk THEN 1 ELSE 0 END) +
            (CASE WHEN team_1_three_pt > team_2_three_pt THEN 1 ELSE 0 END) +
            (CASE WHEN team_1_to < team_2_to THEN 1 ELSE 0 END)
        ) as team_1_categories_won,
        -- Criterios vencidos pelo time 2
        (
            (CASE WHEN team_2_pts > team_1_pts THEN 1 ELSE 0 END) +
            (CASE WHEN team_2_reb > team_1_reb THEN 1 ELSE 0 END) +
            (CASE WHEN team_2_ast > team_1_ast THEN 1 ELSE 0 END) +
            (CASE WHEN team_2_stl > team_1_stl THEN 1 ELSE 0 END) +
            (CASE WHEN team_2_blk > team_1_blk THEN 1 ELSE 0 END) +
            (CASE WHEN team_2_three_pt > team_1_three_pt THEN 1 ELSE 0 END) +
            (CASE WHEN team_2_to < team_1_to THEN 1 ELSE 0 END)
        ) as team_2_categories_won
    FROM game_categories
)
UPDATE fantasy_games fg
SET 
    team_1_points = cc.team_1_categories_won,
    team_2_points = cc.team_2_categories_won
FROM category_counts cc
WHERE fg.fantasy_game_id = cc.fantasy_game_id;

-- ============================================================================
-- Verificacao
-- ============================================================================

-- Mostrar alguns jogos para conferencia
SELECT 
    fantasy_game_id,
    team_1_name,
    team_1_points as cat_won_1,
    team_2_points as cat_won_2,
    team_2_name,
    winner,
    round
FROM fantasy_games
ORDER BY round, fantasy_game_id
LIMIT 20;