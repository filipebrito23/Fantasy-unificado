-- Feature 2 — Recalcular eficiência dos jogadores
-- Seguro para executar após cada importação de fantasy_game_stats.
-- Não altera fantasy_games nem a página/lógica de Classificação.

ALTER TABLE fantasy_game_stats
ADD COLUMN IF NOT EXISTS efficiency NUMERIC;

UPDATE fantasy_game_stats
SET efficiency =
      1.5 * COALESCE(pts, 0)
    + 3.5 * COALESCE(reb, 0)
    + 4.0 * COALESCE(ast, 0)
    + 5.0 * COALESCE(stl, 0)
    + 5.0 * COALESCE(blk, 0)
    + 3.5 * COALESCE(three_pt, 0)
    - 3.5 * COALESCE(turnovers, 0);

-- Conferência rápida.
SELECT
    COUNT(*) AS total_game_stats,
    COUNT(efficiency) AS game_stats_com_efficiency,
    ROUND(AVG(efficiency), 2) AS eficiencia_media
FROM fantasy_game_stats;