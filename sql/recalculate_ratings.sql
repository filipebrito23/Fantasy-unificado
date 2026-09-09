BEGIN;

CREATE TABLE IF NOT EXISTS fantasy_player_game_ratings (
    fantasy_game_stat_id BIGINT PRIMARY KEY
        REFERENCES fantasy_game_stats(fantasy_game_stat_id) ON DELETE CASCADE,
    fantasy_game_id BIGINT NOT NULL
        REFERENCES fantasy_games(fantasy_game_id) ON DELETE CASCADE,
    round INTEGER NOT NULL,
    source_player_id INTEGER NOT NULL,
    team_id INTEGER NOT NULL,
    efficiency DOUBLE PRECISION NOT NULL,
    round_average_efficiency DOUBLE PRECISION NOT NULL,
    rating DOUBLE PRECISION NOT NULL,
    calculated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_player_game_ratings_round
    ON fantasy_player_game_ratings (round, rating DESC);

CREATE INDEX IF NOT EXISTS idx_player_game_ratings_player
    ON fantasy_player_game_ratings (source_player_id, round);

CREATE TABLE IF NOT EXISTS fantasy_team_game_ratings (
    fantasy_game_id BIGINT NOT NULL
        REFERENCES fantasy_games(fantasy_game_id) ON DELETE CASCADE,
    team_id INTEGER NOT NULL,
    round INTEGER NOT NULL,
    team_efficiency DOUBLE PRECISION NOT NULL,
    round_average_efficiency DOUBLE PRECISION NOT NULL,
    rating DOUBLE PRECISION NOT NULL,
    calculated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    PRIMARY KEY (fantasy_game_id, team_id)
);

CREATE INDEX IF NOT EXISTS idx_team_game_ratings_round
    ON fantasy_team_game_ratings (round, rating DESC);

CREATE INDEX IF NOT EXISTS idx_team_game_ratings_team
    ON fantasy_team_game_ratings (team_id, round);

CREATE TABLE IF NOT EXISTS fantasy_round_mvps (
    round INTEGER PRIMARY KEY,
    fantasy_game_stat_id BIGINT NOT NULL
        REFERENCES fantasy_game_stats(fantasy_game_stat_id) ON DELETE CASCADE,
    fantasy_game_id BIGINT NOT NULL
        REFERENCES fantasy_games(fantasy_game_id) ON DELETE CASCADE,
    source_player_id INTEGER NOT NULL,
    team_id INTEGER NOT NULL,
    efficiency DOUBLE PRECISION NOT NULL,
    rating DOUBLE PRECISION NOT NULL,
    calculated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

TRUNCATE TABLE fantasy_player_game_ratings;
TRUNCATE TABLE fantasy_team_game_ratings;
TRUNCATE TABLE fantasy_round_mvps;

INSERT INTO fantasy_player_game_ratings (
    fantasy_game_stat_id,
    fantasy_game_id,
    round,
    source_player_id,
    team_id,
    efficiency,
    round_average_efficiency,
    rating,
    calculated_at
)
SELECT
    fgs.fantasy_game_stat_id,
    fgs.fantasy_game_id,
    fg.round,
    fgs.source_player_id,
    fgs.team_id,
    fgs.efficiency,
    AVG(fgs.efficiency) OVER (PARTITION BY fg.round) AS round_average_efficiency,
    CASE
        WHEN AVG(fgs.efficiency) OVER (PARTITION BY fg.round) = 0 THEN 0
        ELSE ROUND(
            (fgs.efficiency
                / AVG(fgs.efficiency) OVER (PARTITION BY fg.round)
                * 10)::NUMERIC,
            2
        )::DOUBLE PRECISION
    END AS rating,
    NOW()
FROM fantasy_game_stats fgs
JOIN fantasy_games fg
    ON fg.fantasy_game_id = fgs.fantasy_game_id
WHERE fg.round IS NOT NULL
  AND fgs.efficiency IS NOT NULL;

WITH team_games AS (
    SELECT
        fgs.fantasy_game_id,
        fgs.team_id,
        fg.round,
        SUM(fgs.efficiency)::DOUBLE PRECISION AS team_efficiency
    FROM fantasy_game_stats fgs
    JOIN fantasy_games fg
        ON fg.fantasy_game_id = fgs.fantasy_game_id
    WHERE fg.round IS NOT NULL
      AND fgs.efficiency IS NOT NULL
    GROUP BY fgs.fantasy_game_id, fgs.team_id, fg.round
), rated_team_games AS (
    SELECT
        fantasy_game_id,
        team_id,
        round,
        team_efficiency,
        AVG(team_efficiency) OVER (PARTITION BY round) AS round_average_efficiency
    FROM team_games
)
INSERT INTO fantasy_team_game_ratings (
    fantasy_game_id,
    team_id,
    round,
    team_efficiency,
    round_average_efficiency,
    rating,
    calculated_at
)
SELECT
    fantasy_game_id,
    team_id,
    round,
    team_efficiency,
    round_average_efficiency,
    CASE
        WHEN round_average_efficiency = 0 THEN 0
        ELSE ROUND((team_efficiency / round_average_efficiency * 10)::NUMERIC, 2)::DOUBLE PRECISION
    END AS rating,
    NOW()
FROM rated_team_games;

INSERT INTO fantasy_round_mvps (
    round,
    fantasy_game_stat_id,
    fantasy_game_id,
    source_player_id,
    team_id,
    efficiency,
    rating,
    calculated_at
)
SELECT
    ranked.round,
    ranked.fantasy_game_stat_id,
    ranked.fantasy_game_id,
    ranked.source_player_id,
    ranked.team_id,
    ranked.efficiency,
    ranked.rating,
    NOW()
FROM (
    SELECT
        pgr.*,
        fgs.pts,
        fgs.turnovers,
        fp.player_name,
        ROW_NUMBER() OVER (
            PARTITION BY pgr.round
            ORDER BY
                pgr.rating DESC,
                pgr.efficiency DESC,
                fgs.pts DESC,
                fgs.turnovers ASC,
                fp.player_name ASC,
                pgr.fantasy_game_stat_id ASC
        ) AS row_number
    FROM fantasy_player_game_ratings pgr
    JOIN fantasy_game_stats fgs
        ON fgs.fantasy_game_stat_id = pgr.fantasy_game_stat_id
    LEFT JOIN fantasy_players fp
        ON fp.source_player_id = pgr.source_player_id
) ranked
WHERE ranked.row_number = 1;

COMMIT;