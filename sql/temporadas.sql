ALTER TABLE fantasy_player_game_ratings
ADD COLUMN IF NOT EXISTS season TEXT;

ALTER TABLE fantasy_team_game_ratings
ADD COLUMN IF NOT EXISTS season TEXT;

ALTER TABLE fantasy_round_mvps
ADD COLUMN IF NOT EXISTS season TEXT;

aaaaaaaaaaaaaaaaaaaaaaaaaaaaaa



UPDATE fantasy_player_game_ratings
SET season = '2026-27'
WHERE season IS NULL;

UPDATE fantasy_team_game_ratings
SET season = '2026-27'
WHERE season IS NULL;

UPDATE fantasy_round_mvps
SET season = '2026-27'
WHERE season IS NULL;

aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa

CREATE INDEX IF NOT EXISTS idx_player_ratings_season_round
ON fantasy_player_game_ratings (season, round, rating DESC);

CREATE INDEX IF NOT EXISTS idx_player_ratings_season_player
ON fantasy_player_game_ratings (season, source_player_id, round);

CREATE INDEX IF NOT EXISTS idx_team_ratings_season_round
ON fantasy_team_game_ratings (season, round, rating DESC);

CREATE INDEX IF NOT EXISTS idx_team_ratings_season_team
ON fantasy_team_game_ratings (season, team_id, round);

CREATE INDEX IF NOT EXISTS idx_mvps_season_round
ON fantasy_round_mvps (season, round DESC);