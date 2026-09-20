BEGIN;

CREATE TEMP TABLE IF NOT EXISTS current_rating_season (
    season TEXT NOT NULL
);

TRUNCATE current_rating_season;

INSERT INTO current_rating_season (season)
VALUES ('2026-27'); #alterar para a temporada desejada, ou usar uma subquery para pegar a temporada ativa do sistema.


CREATE TABLE IF NOT EXISTS fantasy_player_game_ratings (
    season TEXT NOT NULL,
    fantasy_game_stat_id BIGINT NOT NULL
        REFERENCES fantasy_game_stats(fantasy_game_stat_id)
        ON DELETE CASCADE,
    fantasy_game_id BIGINT NOT NULL
        REFERENCES fantasy_games(fantasy_game_id)
        ON DELETE CASCADE,
    round INTEGER NOT NULL,
    source_player_id INTEGER NOT NULL,
    team_id INTEGER NOT NULL,
    efficiency DOUBLE PRECISION NOT NULL,
    round_average_efficiency DOUBLE PRECISION NOT NULL,
    rating DOUBLE PRECISION NOT NULL,
    calculated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),

    PRIMARY KEY (season, fantasy_game_stat_id)
);


CREATE TABLE IF NOT EXISTS fantasy_team_game_ratings (
    season TEXT NOT NULL,
    fantasy_game_id BIGINT NOT NULL
        REFERENCES fantasy_games(fantasy_game_id)
        ON DELETE CASCADE,
    team_id INTEGER NOT NULL,
    round INTEGER NOT NULL,
    team_efficiency DOUBLE PRECISION NOT NULL,
    round_average_efficiency DOUBLE PRECISION NOT NULL,
    rating DOUBLE PRECISION NOT NULL,
    calculated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),

    PRIMARY KEY (season, fantasy_game_id, team_id)
);


CREATE TABLE IF NOT EXISTS fantasy_round_mvps (
    season TEXT NOT NULL,
    round INTEGER NOT NULL,
    fantasy_game_stat_id BIGINT NOT NULL
        REFERENCES fantasy_game_stats(fantasy_game_stat_id)
        ON DELETE CASCADE,
    fantasy_game_id BIGINT NOT NULL
        REFERENCES fantasy_games(fantasy_game_id)
        ON DELETE CASCADE,
    source_player_id INTEGER NOT NULL,
    team_id INTEGER NOT NULL,
    efficiency DOUBLE PRECISION NOT NULL,
    rating DOUBLE PRECISION NOT NULL,
    calculated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),

    PRIMARY KEY (season, round)
);


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


-- Compatibilidade com tabelas que já existiam sem season.
ALTER TABLE fantasy_player_game_ratings
    ADD COLUMN IF NOT EXISTS season TEXT;

ALTER TABLE fantasy_team_game_ratings
    ADD COLUMN IF NOT EXISTS season TEXT;

ALTER TABLE fantasy_round_mvps
    ADD COLUMN IF NOT EXISTS season TEXT;


-- Preenche registros antigos antes da eventual exclusão/recriação de constraints.
UPDATE fantasy_player_game_ratings
SET season = '2026-27'
WHERE season IS NULL;

UPDATE fantasy_team_game_ratings
SET season = '2026-27'
WHERE season IS NULL;

UPDATE fantasy_round_mvps
SET season = '2026-27'
WHERE season IS NULL;


-- Recalcula apenas a temporada selecionada.
DELETE FROM fantasy_round_mvps
WHERE season IN (
    SELECT season
    FROM current_rating_season
);

DELETE FROM fantasy_team_game_ratings
WHERE season IN (
    SELECT season
    FROM current_rating_season
);

DELETE FROM fantasy_player_game_ratings
WHERE season IN (
    SELECT season
    FROM current_rating_season
);


INSERT INTO fantasy_player_game_ratings (
    season,
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
    crs.season,
    fgs.fantasy_game_stat_id,
    fgs.fantasy_game_id,
    fg.round,
    fgs.source_player_id,
    fgs.team_id,
    fgs.efficiency::DOUBLE PRECISION,
    AVG(fgs.efficiency) OVER (
        PARTITION BY crs.season, fg.round
    )::DOUBLE PRECISION AS round_average_efficiency,
    CASE
        WHEN AVG(fgs.efficiency) OVER (
            PARTITION BY crs.season, fg.round
        ) = 0 THEN 0
        ELSE ROUND(
            (
                fgs.efficiency
                / AVG(fgs.efficiency) OVER (
                    PARTITION BY crs.season, fg.round
                )
                * 10
            )::NUMERIC,
            2
        )::DOUBLE PRECISION
    END AS rating,
    NOW()
FROM fantasy_game_stats fgs
JOIN fantasy_games fg
    ON fg.fantasy_game_id = fgs.fantasy_game_id
JOIN current_rating_season crs
    ON crs.season = fg.season
WHERE fg.round IS NOT NULL
  AND fgs.efficiency IS NOT NULL;


WITH team_games AS (
    SELECT
        crs.season,
        fgs.fantasy_game_id,
        fgs.team_id,
        fg.round,
        SUM(fgs.efficiency)::DOUBLE PRECISION AS team_efficiency
    FROM fantasy_game_stats fgs
    JOIN fantasy_games fg
        ON fg.fantasy_game_id = fgs.fantasy_game_id
    JOIN current_rating_season crs
        ON crs.season = fg.season
    WHERE fg.round IS NOT NULL
      AND fgs.efficiency IS NOT NULL
    GROUP BY
        crs.season,
        fgs.fantasy_game_id,
        fgs.team_id,
        fg.round
),
rated_team_games AS (
    SELECT
        season,
        fantasy_game_id,
        team_id,
        round,
        team_efficiency,
        AVG(team_efficiency) OVER (
            PARTITION BY season, round
        ) AS round_average_efficiency
    FROM team_games
)
INSERT INTO fantasy_team_game_ratings (
    season,
    fantasy_game_id,
    team_id,
    round,
    team_efficiency,
    round_average_efficiency,
    rating,
    calculated_at
)
SELECT
    season,
    fantasy_game_id,
    team_id,
    round,
    team_efficiency,
    round_average_efficiency,
    CASE
        WHEN round_average_efficiency = 0 THEN 0
        ELSE ROUND(
            (
                team_efficiency
                / round_average_efficiency
                * 10
            )::NUMERIC,
            2
        )::DOUBLE PRECISION
    END AS rating,
    NOW()
FROM rated_team_games;


INSERT INTO fantasy_round_mvps (
    season,
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
    ranked.season,
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
            PARTITION BY pgr.season, pgr.round
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
    JOIN current_rating_season crs
        ON crs.season = pgr.season
) ranked
WHERE ranked.row_number = 1;


COMMIT;