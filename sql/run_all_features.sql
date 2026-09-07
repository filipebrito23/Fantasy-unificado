-- ============================================================================
-- FEATURE 3, 4, 5 - Processamento completo dos dados importados
-- ============================================================================

-- ============================================================================
-- FEATURE 3: Eficiencia dos Jogadores
-- ============================================================================

-- Adicionar coluna efficiency se nao existir
ALTER TABLE fantasy_game_stats 
ADD COLUMN IF NOT EXISTS efficiency NUMERIC;

-- Calcular eficiencia para todos os jogadores
-- Formula: 1.5*PTS + 3.5*REB + 4.0*AST + 5.0*STL + 5.0*BLK + 3.5*3PT - 3.5*TO
UPDATE fantasy_game_stats
SET efficiency = 1.5 * pts + 3.5 * reb + 4.0 * ast + 5.0 * stl + 5.0 * blk + 3.5 * three_pt - 3.5 * turnovers;

-- ============================================================================
-- FEATURE 3b: Adicionar coluna winner em fantasy_games (se nao existir)
-- ============================================================================

-- Adicionar coluna winner para armazenar 'A', 'B', ou 'tie'
ALTER TABLE fantasy_games 
ADD COLUMN IF NOT EXISTS winner VARCHAR(10);

-- Calcular vencedor baseado em categorias (PTS, REB, AST, STL, BLK, 3PT, TO)
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
)
UPDATE fantasy_games fg
SET winner = CASE 
    -- Contar vitorias de categorias para time A e B
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

-- ============================================================================
-- FEATURE 3c: Atualizar vencedores dos jogos empatados usando eficiencia
-- ============================================================================

-- Atualizar jogos empatados (winner = 'tie') para usar eficiencia total do time como desempate
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

-- ============================================================================
-- FEATURE 4: Standings / Classificacao
-- ============================================================================

-- Criar tabela fantasy_standings se nao existir
CREATE TABLE IF NOT EXISTS fantasy_standings (
    fantasy_standings_id SERIAL PRIMARY KEY,
    team_id INTEGER NOT NULL,
    team_name VARCHAR(100) NOT NULL,
    round INTEGER NOT NULL,
    wins INTEGER DEFAULT 0,
    losses INTEGER DEFAULT 0,
    ties INTEGER DEFAULT 0,
    points_for NUMERIC DEFAULT 0,
    points_against NUMERIC DEFAULT 0,
    category_wins INTEGER DEFAULT 0,
    category_losses INTEGER DEFAULT 0,
    category_ties INTEGER DEFAULT 0,
    total_efficiency NUMERIC DEFAULT 0,
    source_file VARCHAR(100),
    imported_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW(),
    UNIQUE(team_id, round)
);

-- Limpar standings existentes (opcional - remova se quiser manter historico)
TRUNCATE TABLE fantasy_standings;

-- Popular standings com dados dos jogos
-- Calcula vitorias, derrotas, emportes e estatisticas por time/rodada
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
WITH game_stats_agg AS (
    SELECT 
        fg.fantasy_game_id,
        fg.team_1_id,
        fg.team_1_name,
        fg.team_2_id,
        fg.team_2_name,
        fg.round,
        fg.team_1_points,
        fg.team_2_points,
        fg.winner,
        fg.source_file,
        -- Eficiencia total do time 1
        COALESCE((SELECT SUM(gs.efficiency) FROM fantasy_game_stats gs WHERE gs.fantasy_game_id = fg.fantasy_game_id AND gs.team_id = fg.team_1_id), 0) as team_1_efficiency,
        -- Eficiencia total do time 2
        COALESCE((SELECT SUM(gs.efficiency) FROM fantasy_game_stats gs WHERE gs.fantasy_game_id = fg.fantasy_game_id AND gs.team_id = fg.team_2_id), 0) as team_2_efficiency,
        -- Contar categorias (PTS, REB, AST, STL, BLK, 3PT, TO)
        -- Time 1 venceu PTS?
        CASE WHEN fg.team_1_points > fg.team_2_points THEN 1 ELSE 0 END as team_1_pts_win,
        CASE WHEN fg.team_2_points > fg.team_1_points THEN 1 ELSE 0 END as team_2_pts_win,
        CASE WHEN fg.team_1_points = fg.team_2_points THEN 1 ELSE 0 END as pts_tie
    FROM fantasy_games fg
)
-- Time 1
SELECT 
    team_1_id as team_id,
    team_1_name as team_name,
    round,
    CASE WHEN winner = 'A' THEN 1 ELSE 0 END as wins,
    CASE WHEN winner = 'B' THEN 1 ELSE 0 END as losses,
    CASE WHEN winner = 'tie' THEN 1 ELSE 0 END as ties,
    team_1_points as points_for,
    team_2_points as points_against,
    team_1_pts_win as category_wins,
    team_2_pts_win as category_losses,
    pts_tie as category_ties,
    team_1_efficiency as total_efficiency,
    source_file
FROM game_stats_agg

UNION ALL

-- Time 2
SELECT 
    team_2_id as team_id,
    team_2_name as team_name,
    round,
    CASE WHEN winner = 'B' THEN 1 ELSE 0 END as wins,
    CASE WHEN winner = 'A' THEN 1 ELSE 0 END as losses,
    CASE WHEN winner = 'tie' THEN 1 ELSE 0 END as ties,
    team_2_points as points_for,
    team_1_points as points_against,
    team_2_pts_win as category_wins,
    team_1_pts_win as category_losses,
    pts_tie as category_ties,
    team_2_efficiency as total_efficiency,
    source_file
FROM game_stats_agg

ORDER BY round, team_id;

-- ============================================================================
-- FEATURE 5: Leaderboards / Views
-- ============================================================================

-- View: Top pontuadores por jogo
CREATE OR REPLACE VIEW fantasy_leaderboard_pts AS
SELECT 
    gs.fantasy_game_id,
    fg.round,
    gs.source_player_id,
    fp.player_name,
    gs.team_id,
    t.team_name,
    gs.pts,
    gs.reb,
    gs.ast,
    gs.stl,
    gs.blk,
    gs.three_pt,
    gs.turnovers,
    gs.efficiency
FROM fantasy_game_stats gs
JOIN fantasy_games fg ON fg.fantasy_game_id = gs.fantasy_game_id
JOIN fantasy_players fp ON fp.source_player_id = gs.source_player_id
JOIN teams t ON t.team_id = gs.team_id
ORDER BY gs.pts DESC;

-- View: Top eficiencia por jogo
CREATE OR REPLACE VIEW fantasy_leaderboard_efficiency AS
SELECT 
    gs.fantasy_game_id,
    fg.round,
    gs.source_player_id,
    fp.player_name,
    gs.team_id,
    t.team_name,
    gs.efficiency,
    gs.pts,
    gs.reb,
    gs.ast,
    gs.stl,
    gs.blk,
    gs.three_pt,
    gs.turnovers
FROM fantasy_game_stats gs
JOIN fantasy_games fg ON fg.fantasy_game_id = gs.fantasy_game_id
JOIN fantasy_players fp ON fp.source_player_id = gs.source_player_id
JOIN teams t ON t.team_id = gs.team_id
ORDER BY gs.efficiency DESC;

-- View: Standings consolidado (acumulado por time)
CREATE OR REPLACE VIEW fantasy_standings_total AS
SELECT 
    team_id,
    team_name,
    SUM(wins) as total_wins,
    SUM(losses) as total_losses,
    SUM(ties) as total_ties,
    SUM(points_for) as total_points_for,
    SUM(points_against) as total_points_against,
    SUM(category_wins) as total_category_wins,
    SUM(category_losses) as total_category_losses,
    SUM(category_ties) as total_category_ties,
    SUM(total_efficiency) as total_efficiency,
    COUNT(*) as games_played,
    ROUND(SUM(wins)::NUMERIC / COUNT(*) * 100, 2) as win_percentage
FROM fantasy_standings
GROUP BY team_id, team_name
ORDER BY total_wins DESC, total_category_wins DESC, total_efficiency DESC;

-- View: Media de pontos por jogador (temporada)
CREATE OR REPLACE VIEW fantasy_player_averages AS
SELECT 
    gs.source_player_id,
    fp.player_name,
    gs.team_id,
    t.team_name,
    COUNT(*) as games_played,
    ROUND(AVG(gs.pts), 2) as avg_pts,
    ROUND(AVG(gs.reb), 2) as avg_reb,
    ROUND(AVG(gs.ast), 2) as avg_ast,
    ROUND(AVG(gs.stl), 2) as avg_stl,
    ROUND(AVG(gs.blk), 2) as avg_blk,
    ROUND(AVG(gs.three_pt), 2) as avg_three_pt,
    ROUND(AVG(gs.turnovers), 2) as avg_turnovers,
    ROUND(AVG(gs.efficiency), 2) as avg_efficiency
FROM fantasy_game_stats gs
JOIN fantasy_players fp ON fp.source_player_id = gs.source_player_id
JOIN teams t ON t.team_id = gs.team_id
GROUP BY gs.source_player_id, fp.player_name, gs.team_id, t.team_name
ORDER BY avg_pts DESC;

-- ============================================================================
-- Mensagens de conclusao
-- ============================================================================

-- Contar registros processados
SELECT 'Jogos importados: ' || COUNT(*) as info FROM fantasy_games;
SELECT 'Stats de jogadores: ' || COUNT(*) as info FROM fantasy_game_stats;
SELECT 'Standings por rodada: ' || COUNT(*) as info FROM fantasy_standings;

-- Mostrar top 5 times no standings total
SELECT 'Top 5 Times:' as info;
SELECT * FROM fantasy_standings_total LIMIT 5;

-- Mostrar top 10 jogadores em eficiencia media
SELECT 'Top 10 Jogadores (Eficiencia Media):' as info;
SELECT player_name, team_name, games_played, avg_efficiency FROM fantasy_player_averages LIMIT 10;