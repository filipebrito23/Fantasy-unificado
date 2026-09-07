-- ============================================================================
-- LIMPEZA E RE-IMPORTACAO
-- ============================================================================

-- 1. Deletar jogos sem stats (nao tem dados dos jogadores)
DELETE FROM fantasy_games
WHERE fantasy_game_id NOT IN (
    SELECT DISTINCT fantasy_game_id 
    FROM fantasy_game_stats 
    WHERE fantasy_game_id IS NOT NULL
);

-- 2. Deletar standings orphan (sem jogos correspondentes)
DELETE FROM fantasy_standings
WHERE NOT EXISTS (
    SELECT 1 FROM fantasy_games fg 
    WHERE fg.team_1_id = fantasy_standings.team_id 
       OR fg.team_2_id = fantasy_standings.team_id
);

-- ============================================================================
-- RE-CALCULAR TUDO
-- ============================================================================

-- 3. Re-calcular eficiencia
UPDATE fantasy_game_stats
SET efficiency = 1.5 * pts + 3.5 * reb + 4.0 * ast + 5.0 * stl + 5.0 * blk + 3.5 * three_pt - 3.5 * turnovers
WHERE efficiency IS NULL;

-- 4. Re-calcular winner baseado em categorias
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
)
UPDATE fantasy_games fg
SET 
    team_1_points = (
        (CASE WHEN gc.team_1_pts > gc.team_2_pts THEN 1 ELSE 0 END) +
        (CASE WHEN gc.team_1_reb > gc.team_2_reb THEN 1 ELSE 0 END) +
        (CASE WHEN gc.team_1_ast > gc.team_2_ast THEN 1 ELSE 0 END) +
        (CASE WHEN gc.team_1_stl > gc.team_2_stl THEN 1 ELSE 0 END) +
        (CASE WHEN gc.team_1_blk > gc.team_2_blk THEN 1 ELSE 0 END) +
        (CASE WHEN gc.team_1_three_pt > gc.team_2_three_pt THEN 1 ELSE 0 END) +
        (CASE WHEN gc.team_1_to < gc.team_2_to THEN 1 ELSE 0 END)
    ),
    team_2_points = (
        (CASE WHEN gc.team_2_pts > gc.team_1_pts THEN 1 ELSE 0 END) +
        (CASE WHEN gc.team_2_reb > gc.team_1_reb THEN 1 ELSE 0 END) +
        (CASE WHEN gc.team_2_ast > gc.team_1_ast THEN 1 ELSE 0 END) +
        (CASE WHEN gc.team_2_stl > gc.team_1_stl THEN 1 ELSE 0 END) +
        (CASE WHEN gc.team_2_blk > gc.team_1_blk THEN 1 ELSE 0 END) +
        (CASE WHEN gc.team_2_three_pt > gc.team_1_three_pt THEN 1 ELSE 0 END) +
        (CASE WHEN gc.team_2_to < gc.team_1_to THEN 1 ELSE 0 END)
    ),
    winner = CASE 
        WHEN (
            (CASE WHEN gc.team_1_pts > gc.team_2_pts THEN 1 ELSE 0 END) +
            (CASE WHEN gc.team_1_reb > gc.team_2_reb THEN 1 ELSE 0 END) +
            (CASE WHEN gc.team_1_ast > gc.team_2_ast THEN 1 ELSE 0 END) +
            (CASE WHEN gc.team_1_stl > gc.team_2_stl THEN 1 ELSE 0 END) +
            (CASE WHEN gc.team_1_blk > gc.team_2_blk THEN 1 ELSE 0 END) +
            (CASE WHEN gc.team_1_three_pt > gc.team_2_three_pt THEN 1 ELSE 0 END) +
            (CASE WHEN gc.team_1_to < gc.team_2_to THEN 1 ELSE 0 END)
        ) > (
            (CASE WHEN gc.team_2_pts > gc.team_1_pts THEN 1 ELSE 0 END) +
            (CASE WHEN gc.team_2_reb > gc.team_1_reb THEN 1 ELSE 0 END) +
            (CASE WHEN gc.team_2_ast > gc.team_1_ast THEN 1 ELSE 0 END) +
            (CASE WHEN gc.team_2_stl > gc.team_1_stl THEN 1 ELSE 0 END) +
            (CASE WHEN gc.team_2_blk > gc.team_1_blk THEN 1 ELSE 0 END) +
            (CASE WHEN gc.team_2_three_pt > gc.team_1_three_pt THEN 1 ELSE 0 END) +
            (CASE WHEN gc.team_2_to < gc.team_1_to THEN 1 ELSE 0 END)
        ) THEN 'A'
        WHEN (
            (CASE WHEN gc.team_2_pts > gc.team_1_pts THEN 1 ELSE 0 END) +
            (CASE WHEN gc.team_2_reb > gc.team_1_reb THEN 1 ELSE 0 END) +
            (CASE WHEN gc.team_2_ast > gc.team_1_ast THEN 1 ELSE 0 END) +
            (CASE WHEN gc.team_2_stl > gc.team_1_stl THEN 1 ELSE 0 END) +
            (CASE WHEN gc.team_2_blk > gc.team_1_blk THEN 1 ELSE 0 END) +
            (CASE WHEN gc.team_2_three_pt > gc.team_1_three_pt THEN 1 ELSE 0 END) +
            (CASE WHEN gc.team_2_to < gc.team_1_to THEN 1 ELSE 0 END)
        ) > (
            (CASE WHEN gc.team_1_pts > gc.team_2_pts THEN 1 ELSE 0 END) +
            (CASE WHEN gc.team_1_reb > gc.team_2_reb THEN 1 ELSE 0 END) +
            (CASE WHEN gc.team_1_ast > gc.team_2_ast THEN 1 ELSE 0 END) +
            (CASE WHEN gc.team_1_stl > gc.team_2_stl THEN 1 ELSE 0 END) +
            (CASE WHEN gc.team_1_blk > gc.team_2_blk THEN 1 ELSE 0 END) +
            (CASE WHEN gc.team_1_three_pt > gc.team_2_three_pt THEN 1 ELSE 0 END) +
            (CASE WHEN gc.team_1_to < gc.team_2_to THEN 1 ELSE 0 END)
        ) THEN 'B'
        ELSE 'tie'
    END
FROM game_categories gc
WHERE fg.fantasy_game_id = gc.fantasy_game_id;

-- 5. Atualizar jogos empatados usando eficiencia como desempate
WITH team_efficiency AS (
    SELECT 
        gs.fantasy_game_id,
        gs.team_id,
        SUM(gs.efficiency) as total_efficiency
    FROM fantasy_game_stats gs
    GROUP BY gs.fantasy_game_id, gs.team_id
),
game_efficiencies AS (
    SELECT 
        fg.fantasy_game_id,
        fg.team_1_id,
        fg.team_2_id,
        COALESCE(te1.total_efficiency, 0) as team_1_efficiency,
        COALESCE(te2.total_efficiency, 0) as team_2_efficiency
    FROM fantasy_games fg
    LEFT JOIN team_efficiency te1 ON te1.fantasy_game_id = fg.fantasy_game_id AND te1.team_id = fg.team_1_id
    LEFT JOIN team_efficiency te2 ON te2.fantasy_game_id = fg.fantasy_game_id AND te2.team_id = fg.team_2_id
    WHERE fg.winner = 'tie'
)
UPDATE fantasy_games fg
SET winner = CASE 
    WHEN ge.team_1_efficiency > ge.team_2_efficiency THEN 'A'
    WHEN ge.team_2_efficiency > ge.team_1_efficiency THEN 'B'
    ELSE 'tie'
END
FROM game_efficiencies ge
WHERE fg.fantasy_game_id = ge.fantasy_game_id
  AND fg.winner = 'tie';

-- 6. Re-popular standings
TRUNCATE TABLE fantasy_standings;

INSERT INTO fantasy_standings (
    team_id,
    team_name,
    round,
    wins,
    losses,
    ties,
    points_for,
    points_against,
    category_wins,
    category_losses,
    category_ties,
    total_efficiency,
    source_file
)
SELECT 
    fg.team_1_id as team_id,
    fg.team_1_name as team_name,
    fg.round,
    CASE WHEN fg.winner = 'A' THEN 1 ELSE 0 END as wins,
    CASE WHEN fg.winner = 'B' THEN 1 ELSE 0 END as losses,
    CASE WHEN fg.winner = 'tie' THEN 1 ELSE 0 END as ties,
    fg.team_1_points as points_for,
    fg.team_2_points as points_against,
    fg.team_1_points as category_wins,
    fg.team_2_points as category_losses,
    CASE WHEN fg.team_1_points = fg.team_2_points THEN 1 ELSE 0 END as category_ties,
    COALESCE((SELECT SUM(gs.efficiency) FROM fantasy_game_stats gs WHERE gs.fantasy_game_id = fg.fantasy_game_id AND gs.team_id = fg.team_1_id), 0) as total_efficiency,
    fg.source_file
FROM fantasy_games fg

UNION ALL

SELECT 
    fg.team_2_id as team_id,
    fg.team_2_name as team_name,
    fg.round,
    CASE WHEN fg.winner = 'B' THEN 1 ELSE 0 END as wins,
    CASE WHEN fg.winner = 'A' THEN 1 ELSE 0 END as losses,
    CASE WHEN fg.winner = 'tie' THEN 1 ELSE 0 END as ties,
    fg.team_2_points as points_for,
    fg.team_1_points as points_against,
    fg.team_2_points as category_wins,
    fg.team_1_points as category_losses,
    CASE WHEN fg.team_1_points = fg.team_2_points THEN 1 ELSE 0 END as category_ties,
    COALESCE((SELECT SUM(gs.efficiency) FROM fantasy_game_stats gs WHERE gs.fantasy_game_id = fg.fantasy_game_id AND gs.team_id = fg.team_2_id), 0) as total_efficiency,
    fg.source_file
FROM fantasy_games fg

ORDER BY round, team_id;

-- ============================================================================
-- VERIFICACAO
-- ============================================================================

-- Contar jogos com stats
SELECT 'Jogos com stats: ' || COUNT(DISTINCT fantasy_game_id) as info FROM fantasy_game_stats;

-- Contar jogos sem stats
SELECT 'Jogos sem stats: ' || COUNT(*) as info 
FROM fantasy_games 
WHERE fantasy_game_id NOT IN (SELECT DISTINCT fantasy_game_id FROM fantasy_game_stats);

-- Mostrar alguns jogos
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
LIMIT 30;

-- Top 5 standings
SELECT * FROM fantasy_standings_total LIMIT 5;