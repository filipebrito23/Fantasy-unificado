-- Limpar stats de jogadores (dados de teste)
DELETE FROM fantasy_game_stats;

-- Opcional: limpar standings (serao recalculados quando importar dados reais)
DELETE FROM fantasy_standings;

-- Opcional: resetar sequencias (se quiser IDs comecando do 1)
-- ALTER SEQUENCE fantasy_game_stats_fantasy_game_stat_id_seq RESTART WITH 1;
-- ALTER SEQUENCE fantasy_standings_fantasy_standings_id_seq RESTART WITH 1;

#melhor opcao para resetar as tabelas e sequencias de uma vez so, sem precisar deletar linha por linha

TRUNCATE TABLE
    fantasy_round_mvps,
    fantasy_team_game_ratings,
    fantasy_player_game_ratings,
    fantasy_game_stats,
    fantasy_games
CASCADE;

ou

DELETE FROM fantasy_round_mvps
WHERE season = '2026-27';

DELETE FROM fantasy_team_game_ratings
WHERE season = '2026-27';

DELETE FROM fantasy_player_game_ratings
WHERE season = '2026-27';