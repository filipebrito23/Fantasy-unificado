-- Limpar stats de jogadores (dados de teste)
DELETE FROM fantasy_game_stats;

-- Opcional: limpar standings (serao recalculados quando importar dados reais)
DELETE FROM fantasy_standings;

-- Opcional: resetar sequencias (se quiser IDs comecando do 1)
-- ALTER SEQUENCE fantasy_game_stats_fantasy_game_stat_id_seq RESTART WITH 1;
-- ALTER SEQUENCE fantasy_standings_fantasy_standings_id_seq RESTART WITH 1;