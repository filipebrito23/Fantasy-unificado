
-- Confirmed target table:
-- fantasy_roster_seasons
-- Confirmed team table:
-- teams
-- Pick rule is intentionally not handled here:
-- pick year 2026 corresponds to season 2026-27.

-- The migration assumes fantasy_roster_seasons was created with these columns:
-- team_id, source_player_id, season, roster_type, roster_order,
-- salary, team_option, source_table, source_row_id,
-- source_file, source_sheet, imported_at, updated_at.

BEGIN;

INSERT INTO fantasy_roster_seasons (
    team_id,
    source_player_id,
    season,
    roster_type,
    roster_order,
    salary,
    team_option,
    source_table,
    source_row_id,
    source_file,
    source_sheet,
    imported_at,
    updated_at
)
SELECT
    r.team_id,
    r.source_player_id,
    x.season,
    'main' AS roster_type,
    r.roster_order,
    x.salary,
    CASE
        WHEN LOWER(BTRIM(COALESCE(x.team_option, ''))) IN
             ('sim', 'yes', 'true', '1', 'option')
        THEN TRUE
        ELSE FALSE
    END AS team_option,
    'fantasy_roster' AS source_table,
    r.fantasy_roster_id AS source_row_id,
    r.source_file,
    r.source_sheet,
    r.imported_at,
    r.updated_at
FROM fantasy_roster r
CROSS JOIN LATERAL (
    VALUES
        ('2026-27'::TEXT, r.salarie_26_27, r.option_26_27),
        ('2027-28'::TEXT, r.salarie_27_28, r.option_27_28),
        ('2028-29'::TEXT, r.salarie_28_29, r.option_28_29),
        ('2029-30'::TEXT, r.salarie_29_30, r.option_29_30)
) AS x(season, salary, team_option)
ON CONFLICT (team_id, source_player_id, season, roster_type)
DO UPDATE SET
    roster_order = EXCLUDED.roster_order,
    salary = EXCLUDED.salary,
    team_option = EXCLUDED.team_option,
    source_table = EXCLUDED.source_table,
    source_row_id = EXCLUDED.source_row_id,
    source_file = EXCLUDED.source_file,
    source_sheet = EXCLUDED.source_sheet,
    imported_at = EXCLUDED.imported_at,
    updated_at = EXCLUDED.updated_at;


INSERT INTO fantasy_roster_seasons (
    team_id,
    source_player_id,
    season,
    roster_type,
    roster_order,
    salary,
    team_option,
    source_table,
    source_row_id,
    source_file,
    source_sheet,
    imported_at,
    updated_at
)
SELECT
    d.team_id,
    d.source_player_id,
    x.season,
    'development' AS roster_type,
    d.roster_order,
    x.salary,
    CASE
        WHEN LOWER(BTRIM(COALESCE(x.team_option, ''))) IN
             ('sim', 'yes', 'true', '1', 'option')
        THEN TRUE
        ELSE FALSE
    END AS team_option,
    'fantasy_development' AS source_table,
    d.fantasy_development_id AS source_row_id,
    d.source_file,
    d.source_sheet,
    d.imported_at,
    d.updated_at
FROM fantasy_development d
CROSS JOIN LATERAL (
    VALUES
        ('2026-27'::TEXT, d.salarie_26_27, d.option_26_27),
        ('2027-28'::TEXT, d.salarie_27_28, d.option_27_28),
        ('2028-29'::TEXT, d.salarie_28_29, d.option_28_29),
        ('2029-30'::TEXT, d.salarie_29_30, d.option_29_30)
) AS x(season, salary, team_option)
ON CONFLICT (team_id, source_player_id, season, roster_type)
DO UPDATE SET
    roster_order = EXCLUDED.roster_order,
    salary = EXCLUDED.salary,
    team_option = EXCLUDED.team_option,
    source_table = EXCLUDED.source_table,
    source_row_id = EXCLUDED.source_row_id,
    source_file = EXCLUDED.source_file,
    source_sheet = EXCLUDED.source_sheet,
    imported_at = EXCLUDED.imported_at,
    updated_at = EXCLUDED.updated_at;


CREATE INDEX IF NOT EXISTS idx_roster_seasons_season
    ON fantasy_roster_seasons (season);

CREATE INDEX IF NOT EXISTS idx_roster_seasons_team_season
    ON fantasy_roster_seasons (team_id, season);

CREATE INDEX IF NOT EXISTS idx_roster_seasons_player_season
    ON fantasy_roster_seasons (source_player_id, season);

CREATE INDEX IF NOT EXISTS idx_roster_seasons_type_season
    ON fantasy_roster_seasons (roster_type, season);

COMMIT;