from __future__ import annotations

import sys
from pathlib import Path
from typing import Any

import pandas as pd
from sqlalchemy import text

# Permite importar app_lib ao executar:
# python scripts/import_roster_to_neon.py
PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

from app_lib.db_v5 import engine, healthcheck_db_v5, is_postgres_v5
import re


def normalize_pick_id(value: Any) -> str | None:
    """
    Padroniza IDs de picks em um formato único.

    Exemplos:
    P2026R1T5      -> P2026R1T05
    P2026_R1_T5    -> P2026R1T05
    p2026-r1-t05   -> P2026R1T05
    P2027 R2 T14   -> P2027R2T14

    Se não conseguir reconhecer o padrão, mantém o texto original
    em caixa alta e sem espaços, para não perder informação.
    """
    raw = clean_text(value)

    if not raw:
        return None

    compact = (
        raw.upper()
        .strip()
        .replace(" ", "")
        .replace("_", "")
        .replace("-", "")
    )

    match = re.fullmatch(r"P?(\d{4})R?(\d{1,2})T?(\d{1,2})", compact)

    if not match:
        return compact

    year, round_number, team_id = match.groups()

    return f"P{int(year):04d}R{int(round_number)}T{int(team_id):02d}"

WORKBOOK_PATH = PROJECT_ROOT / "roster.xlsx"
SOURCE_FILE_NAME = WORKBOOK_PATH.name

SEASON_KEYS = ("26_27", "27_28", "28_29", "29_30")

SHEET_ALIASES = {
    "players": "players",
    "teams": "teams",
    "roster": "roster",
    "development": "development",
    "fines": "fines",
    "picks": "picks",
    "transactions": "transactions",
    "transactionitems": "transactionitems",
    "games": "games",
    "Semana": "Semana",
}


def normalize_col_name(column: Any) -> str:
    """
    Converte aliases de coluna do Excel para os nomes esperados
    pela aplicação e pelo banco Neon.
    """
    raw = str(column).strip()

    if raw.lower().startswith("unnamed"):
        return ""

    key = (
        raw.lower()
        .strip()
        .replace(" ", "")
        .replace("-", "")
        .replace("/", "")
        .replace("_", "")
    )

    aliases = {
        "teamid": "team_id",
        "teamname": "team_name",
        "managername": "manager_name",

        "playerid": "player_id",
        "playername": "player_name",
        "nbateam": "nba_team",
        "position": "position",

        "rosterorder": "roster_order",
        "posorder": "pos_order",
        "order": "order",

        "pickid": "pick_id",
        "originalteampickid": "original_team_pick_id",
        "currentteamownerid": "current_team_owner_id",

        "transactionid": "transaction_id",
        "transactiontype": "transaction_type",
        "transactiondate": "transaction_date",
        "fromteamid": "from_team_id",
        "toteamid": "to_team_id",
        "initiatedby": "initiated_by",

        "itemid": "item_id",
        "itemtype": "item_type",
        "assetid": "asset_id",
        "fromrostertype": "from_roster_type",
        "torostertype": "to_roster_type",
        "effectiveseason": "effective_season",
        "itemnotes": "item_notes",

        "idjogo": "id_jogo",
        "idtime1": "id_time_1",
        "nometime1": "nome_time_1",
        "pontostime1": "pontos_time_1",
        "pontostime2": "pontos_time_2",
        "idtime2": "id_time_2",
        "nometime2": "nome_time_2",
        "rodada": "rodada",

        "semananum": "semana_num",
        "semanainicio": "semana_inicio",
        "teamabbr": "team_abbr",
        "jogonasemana": "jogo_na_semana",
        "gamedate": "game_date",
        "gameid": "game_id",
        "opponentabbr": "opponent_abbr",
        "opponentname": "opponent_name",
        "homeaway": "home_away",

        "pts": "pts",
        "trb": "trb",
        "ast": "ast",
        "stl": "stl",
        "blk": "blk",
        "threep": "three_p",
        "tov": "tov",
        "status": "status",
        "fantasyvalue": "fantasy_value",
        "notes": "notes",
        "season": "season",
        "round": "round",
    }

    if key in aliases:
        return aliases[key]

    # Salários e opções: salarie2627 -> salarie_26_27
    for season in SEASON_KEYS:
        compact = season.replace("_", "")

        if key in {
            f"salarie{compact}",
            f"salary{compact}",
            f"salario{compact}",
        }:
            return f"salarie_{season}"

        if key in {
            f"option{compact}",
            f"opcao{compact}",
        }:
            return f"option_{season}"

        if key in {
            f"fine{compact}",
            f"multa{compact}",
        }:
            return f"fine_{season}"

    return raw


def normalize_columns(df: pd.DataFrame) -> pd.DataFrame:
    """
    Normaliza nomes de coluna, remove colunas Unnamed e resolve
    duplicatas de coluna preservando o primeiro valor não nulo.
    """
    if df.empty:
        return df.copy()

    out = df.copy()
    out.columns = [normalize_col_name(col) for col in out.columns]
    out = out.loc[:, [col for col in out.columns if col != ""]]

    if out.columns.duplicated().any():
        merged = pd.DataFrame(index=out.index)

        for col in pd.unique(out.columns):
            candidates = out.loc[:, out.columns == col]

            if isinstance(candidates, pd.Series):
                merged[col] = candidates
            elif candidates.shape[1] == 1:
                merged[col] = candidates.iloc[:, 0]
            else:
                merged[col] = candidates.bfill(axis=1).iloc[:, 0]

        out = merged

    return out


def read_sheet(workbook: pd.ExcelFile, sheet_name: str) -> pd.DataFrame:
    """
    Lê e normaliza uma aba. Se a aba não existir, retorna DataFrame vazio.
    """
    if sheet_name not in workbook.sheet_names:
        print(f"[AVISO] Aba ausente: {sheet_name}")
        return pd.DataFrame()

    df = pd.read_excel(workbook, sheet_name=sheet_name)
    return normalize_columns(df)


def clean_text(value: Any) -> str | None:
    if value is None or pd.isna(value):
        return None

    text_value = str(value).strip()
    if not text_value or text_value.lower() in {"nan", "none", "null"}:
        return None

    return text_value


def to_int(value: Any) -> int | None:
    if value is None or pd.isna(value):
        return None

    try:
        return int(float(value))
    except (TypeError, ValueError):
        return None


def to_float(value: Any) -> float | None:
    if value is None or pd.isna(value):
        return None

    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def to_date(value: Any):
    if value is None or pd.isna(value):
        return None

    parsed = pd.to_datetime(value, errors="coerce")
    if pd.isna(parsed):
        return None

    return parsed.date()


def get_value(row: pd.Series, column: str, default: Any = None) -> Any:
    if column not in row.index:
        return default

    value = row.get(column, default)

    if isinstance(value, pd.Series):
        value = value.dropna().iloc[0] if not value.dropna().empty else default

    return value


def validate_required_columns(
    df: pd.DataFrame,
    sheet_name: str,
    required: set[str],
) -> list[str]:
    missing = sorted(required - set(df.columns))
    if missing:
        return [
            f"Aba '{sheet_name}' sem colunas obrigatórias: "
            + ", ".join(missing)
        ]
    return []


def ensure_fantasy_teams(
    teams_df: pd.DataFrame,
    source_file: str,
) -> tuple[int, list[str]]:
    """
    Os times já são utilizados por auth/leilão, então não criamos fantasy_teams.
    Em vez disso, sincronizamos somente os nomes no cadastro teams existente,
    sem alterar cap_limit já existente.
    """
    errors: list[str] = []
    imported = 0

    required = {"team_id", "team_name"}
    errors.extend(validate_required_columns(teams_df, "teams", required))

    if errors:
        return imported, errors

    rows: list[dict[str, Any]] = []

    for index, row in teams_df.iterrows():
        team_id = to_int(get_value(row, "team_id"))
        team_name = clean_text(get_value(row, "team_name"))

        if team_id is None or not team_name:
            errors.append(f"teams linha {index + 2}: team_id ou team_name inválido.")
            continue

        rows.append(
            {
                "team_id": team_id,
                "team_name": team_name,
            }
        )

    if not rows:
        return imported, errors

    with engine.begin() as conn:
        for row in rows:
            exists = conn.execute(
                text(
                    """
                    SELECT team_id
                    FROM teams
                    WHERE team_id = :team_id
                    """
                ),
                {"team_id": row["team_id"]},
            ).scalar()

            if exists is None:
                conn.execute(
                    text(
                        """
                        INSERT INTO teams (team_id, team_name, cap_limit)
                        VALUES (:team_id, :team_name, :cap_limit)
                        """
                    ),
                    {
                        "team_id": row["team_id"],
                        "team_name": row["team_name"],
                        "cap_limit": 110_000_000,
                    },
                )
            else:
                conn.execute(
                    text(
                        """
                        UPDATE teams
                        SET team_name = :team_name
                        WHERE team_id = :team_id
                        """
                    ),
                    row,
                )

            imported += 1

    return imported, errors


def import_fantasy_players(
    players_df: pd.DataFrame,
    source_file: str,
) -> tuple[int, list[str]]:
    errors: list[str] = []
    imported = 0

    required = {"player_id", "player_name", "position"}
    errors.extend(validate_required_columns(players_df, "players", required))

    if errors:
        return imported, errors

    rows: list[dict[str, Any]] = []

    for index, row in players_df.iterrows():
        source_player_id = to_int(get_value(row, "player_id"))
        player_name = clean_text(get_value(row, "player_name"))
        position = clean_text(get_value(row, "position"))

        if source_player_id is None or not player_name or not position:
            errors.append(
                f"players linha {index + 2}: "
                "player_id, player_name ou position inválido."
            )
            continue

        rows.append(
            {
                "source_player_id": source_player_id,
                "player_name": player_name,
                "nba_team": clean_text(get_value(row, "nba_team")),
                "position": position,
                "pts": to_float(get_value(row, "pts")),
                "trb": to_float(get_value(row, "trb")),
                "ast": to_float(get_value(row, "ast")),
                "stl": to_float(get_value(row, "stl")),
                "blk": to_float(get_value(row, "blk")),
                "three_p": to_float(get_value(row, "three_p")),
                "tov": to_float(get_value(row, "tov")),
                "status": clean_text(get_value(row, "status")),
                "fantasy_value": to_float(get_value(row, "fantasy_value")),
                "source_file": source_file,
            }
        )

    with engine.begin() as conn:
        for row in rows:
            conn.execute(
                text(
                    """
                    INSERT INTO fantasy_players (
                        source_player_id,
                        player_name,
                        nba_team,
                        position,
                        pts,
                        trb,
                        ast,
                        stl,
                        blk,
                        three_p,
                        tov,
                        status,
                        fantasy_value,
                        source_file,
                        source_sheet,
                        imported_at,
                        updated_at
                    )
                    VALUES (
                        :source_player_id,
                        :player_name,
                        :nba_team,
                        :position,
                        :pts,
                        :trb,
                        :ast,
                        :stl,
                        :blk,
                        :three_p,
                        :tov,
                        :status,
                        :fantasy_value,
                        :source_file,
                        'players',
                        NOW(),
                        NOW()
                    )
                    ON CONFLICT (source_player_id)
                    DO UPDATE SET
                        player_name = EXCLUDED.player_name,
                        nba_team = EXCLUDED.nba_team,
                        position = EXCLUDED.position,
                        pts = EXCLUDED.pts,
                        trb = EXCLUDED.trb,
                        ast = EXCLUDED.ast,
                        stl = EXCLUDED.stl,
                        blk = EXCLUDED.blk,
                        three_p = EXCLUDED.three_p,
                        tov = EXCLUDED.tov,
                        status = EXCLUDED.status,
                        fantasy_value = EXCLUDED.fantasy_value,
                        source_file = EXCLUDED.source_file,
                        source_sheet = EXCLUDED.source_sheet,
                        imported_at = NOW(),
                        updated_at = NOW()
                    """
                ),
                row,
            )
            imported += 1

    return imported, errors


def build_roster_rows(
    df: pd.DataFrame,
    sheet_name: str,
    source_file: str,
) -> tuple[list[dict[str, Any]], list[str]]:
    errors: list[str] = []

    required = {"team_id", "player_id"}
    errors.extend(validate_required_columns(df, sheet_name, required))

    if errors:
        return [], errors

    rows: list[dict[str, Any]] = []

    for index, row in df.iterrows():
        team_id = to_int(get_value(row, "team_id"))
        source_player_id = to_int(get_value(row, "player_id"))

        if team_id is None or source_player_id is None:
            errors.append(
                f"{sheet_name} linha {index + 2}: "
                "team_id ou player_id inválido."
            )
            continue

        rows.append(
            {
                "team_id": team_id,
                "source_player_id": source_player_id,
                "roster_order": (
                    to_int(get_value(row, "roster_order"))
                    or to_int(get_value(row, "pos_order"))
                    or to_int(get_value(row, "order"))
                ),
                "salarie_26_27": to_float(get_value(row, "salarie_26_27")),
                "option_26_27": clean_text(get_value(row, "option_26_27")),
                "salarie_27_28": to_float(get_value(row, "salarie_27_28")),
                "option_27_28": clean_text(get_value(row, "option_27_28")),
                "salarie_28_29": to_float(get_value(row, "salarie_28_29")),
                "option_28_29": clean_text(get_value(row, "option_28_29")),
                "salarie_29_30": to_float(get_value(row, "salarie_29_30")),
                "option_29_30": clean_text(get_value(row, "option_29_30")),
                "source_file": source_file,
                "source_sheet": sheet_name,
            }
        )

    return rows, errors


def import_fantasy_roster(
    roster_df: pd.DataFrame,
    source_file: str,
) -> tuple[int, list[str]]:
    rows, errors = build_roster_rows(roster_df, "roster", source_file)

    imported = 0

    with engine.begin() as conn:
        for row in rows:
            conn.execute(
                text(
                    """
                    INSERT INTO fantasy_roster (
                        team_id,
                        source_player_id,
                        roster_order,
                        salarie_26_27,
                        option_26_27,
                        salarie_27_28,
                        option_27_28,
                        salarie_28_29,
                        option_28_29,
                        salarie_29_30,
                        option_29_30,
                        source_file,
                        source_sheet,
                        imported_at,
                        updated_at
                    )
                    VALUES (
                        :team_id,
                        :source_player_id,
                        :roster_order,
                        :salarie_26_27,
                        :option_26_27,
                        :salarie_27_28,
                        :option_27_28,
                        :salarie_28_29,
                        :option_28_29,
                        :salarie_29_30,
                        :option_29_30,
                        :source_file,
                        :source_sheet,
                        NOW(),
                        NOW()
                    )
                    ON CONFLICT (team_id, source_player_id)
                    DO UPDATE SET
                        roster_order = EXCLUDED.roster_order,
                        salarie_26_27 = EXCLUDED.salarie_26_27,
                        option_26_27 = EXCLUDED.option_26_27,
                        salarie_27_28 = EXCLUDED.salarie_27_28,
                        option_27_28 = EXCLUDED.option_27_28,
                        salarie_28_29 = EXCLUDED.salarie_28_29,
                        option_28_29 = EXCLUDED.option_28_29,
                        salarie_29_30 = EXCLUDED.salarie_29_30,
                        option_29_30 = EXCLUDED.option_29_30,
                        source_file = EXCLUDED.source_file,
                        source_sheet = EXCLUDED.source_sheet,
                        imported_at = NOW(),
                        updated_at = NOW()
                    """
                ),
                row,
            )
            imported += 1

    return imported, errors


def import_fantasy_development(
    development_df: pd.DataFrame,
    source_file: str,
) -> tuple[int, list[str]]:
    rows, errors = build_roster_rows(
        development_df,
        "development",
        source_file,
    )

    imported = 0

    with engine.begin() as conn:
        for row in rows:
            conn.execute(
                text(
                    """
                    INSERT INTO fantasy_development (
                        team_id,
                        source_player_id,
                        roster_order,
                        salarie_26_27,
                        option_26_27,
                        salarie_27_28,
                        option_27_28,
                        salarie_28_29,
                        option_28_29,
                        salarie_29_30,
                        option_29_30,
                        source_file,
                        source_sheet,
                        imported_at,
                        updated_at
                    )
                    VALUES (
                        :team_id,
                        :source_player_id,
                        :roster_order,
                        :salarie_26_27,
                        :option_26_27,
                        :salarie_27_28,
                        :option_27_28,
                        :salarie_28_29,
                        :option_28_29,
                        :salarie_29_30,
                        :option_29_30,
                        :source_file,
                        :source_sheet,
                        NOW(),
                        NOW()
                    )
                    ON CONFLICT (team_id, source_player_id)
                    DO UPDATE SET
                        roster_order = EXCLUDED.roster_order,
                        salarie_26_27 = EXCLUDED.salarie_26_27,
                        option_26_27 = EXCLUDED.option_26_27,
                        salarie_27_28 = EXCLUDED.salarie_27_28,
                        option_27_28 = EXCLUDED.option_27_28,
                        salarie_28_29 = EXCLUDED.salarie_28_29,
                        option_28_29 = EXCLUDED.option_28_29,
                        salarie_29_30 = EXCLUDED.salarie_29_30,
                        option_29_30 = EXCLUDED.option_29_30,
                        source_file = EXCLUDED.source_file,
                        source_sheet = EXCLUDED.source_sheet,
                        imported_at = NOW(),
                        updated_at = NOW()
                    """
                ),
                row,
            )
            imported += 1

    return imported, errors


def import_fantasy_fines(
    fines_df: pd.DataFrame,
    source_file: str,
) -> tuple[int, list[str]]:
    errors: list[str] = []
    imported = 0

    required = {"team_id"}
    errors.extend(validate_required_columns(fines_df, "fines", required))

    if errors:
        return imported, errors

    with engine.begin() as conn:
        for index, row in fines_df.iterrows():
            team_id = to_int(get_value(row, "team_id"))

            if team_id is None:
                errors.append(f"fines linha {index + 2}: team_id inválido.")
                continue

            payload = {
                "team_id": team_id,
                "fine_26_27": to_float(get_value(row, "fine_26_27")) or 0.0,
                "fine_27_28": to_float(get_value(row, "fine_27_28")) or 0.0,
                "fine_28_29": to_float(get_value(row, "fine_28_29")) or 0.0,
                "fine_29_30": to_float(get_value(row, "fine_29_30")) or 0.0,
                "notes": clean_text(get_value(row, "notes")),
                "source_file": source_file,
            }

            conn.execute(
                text(
                    """
                    INSERT INTO fantasy_fines (
                        team_id,
                        fine_26_27,
                        fine_27_28,
                        fine_28_29,
                        fine_29_30,
                        notes,
                        source_file,
                        source_sheet,
                        imported_at,
                        updated_at
                    )
                    VALUES (
                        :team_id,
                        :fine_26_27,
                        :fine_27_28,
                        :fine_28_29,
                        :fine_29_30,
                        :notes,
                        :source_file,
                        'fines',
                        NOW(),
                        NOW()
                    )
                    ON CONFLICT (team_id)
                    DO UPDATE SET
                        fine_26_27 = EXCLUDED.fine_26_27,
                        fine_27_28 = EXCLUDED.fine_27_28,
                        fine_28_29 = EXCLUDED.fine_28_29,
                        fine_29_30 = EXCLUDED.fine_29_30,
                        notes = EXCLUDED.notes,
                        source_file = EXCLUDED.source_file,
                        source_sheet = EXCLUDED.source_sheet,
                        imported_at = NOW(),
                        updated_at = NOW()
                    """
                ),
                payload,
            )

            imported += 1

    return imported, errors


def import_fantasy_picks(
    picks_df: pd.DataFrame,
    source_file: str,
) -> tuple[int, list[str]]:
    errors: list[str] = []
    imported = 0

    required = {
        "pick_id",
        "original_team_pick_id",
        "round",
        "year",
        "current_team_owner_id",
    }
    errors.extend(validate_required_columns(picks_df, "picks", required))

    if errors:
        return imported, errors

    with engine.begin() as conn:
        for index, row in picks_df.iterrows():
            source_pick_id = normalize_pick_id(get_value(row, "pick_id"))
            original_team_pick_id = to_int(
                get_value(row, "original_team_pick_id")
            )
            pick_round = to_int(get_value(row, "round"))
            pick_year = to_int(get_value(row, "year"))
            current_team_owner_id = to_int(
                get_value(row, "current_team_owner_id")
            )

            if (
                not source_pick_id
                or original_team_pick_id is None
                or pick_round is None
                or pick_year is None
                or current_team_owner_id is None
            ):
                errors.append(
                    f"picks linha {index + 2}: dados obrigatórios inválidos."
                )
                continue

            payload = {
                "source_pick_id": source_pick_id,
                "original_team_pick_id": original_team_pick_id,
                "round": pick_round,
                "year": pick_year,
                "current_team_owner_id": current_team_owner_id,
                "source_file": source_file,
            }

            conn.execute(
                text(
                    """
                    INSERT INTO fantasy_picks (
                        source_pick_id,
                        original_team_pick_id,
                        round,
                        year,
                        current_team_owner_id,
                        source_file,
                        source_sheet,
                        imported_at,
                        updated_at
                    )
                    VALUES (
                        :source_pick_id,
                        :original_team_pick_id,
                        :round,
                        :year,
                        :current_team_owner_id,
                        :source_file,
                        'picks',
                        NOW(),
                        NOW()
                    )
                    ON CONFLICT (source_pick_id)
                    DO UPDATE SET
                        original_team_pick_id = EXCLUDED.original_team_pick_id,
                        round = EXCLUDED.round,
                        year = EXCLUDED.year,
                        current_team_owner_id = EXCLUDED.current_team_owner_id,
                        source_file = EXCLUDED.source_file,
                        source_sheet = EXCLUDED.source_sheet,
                        imported_at = NOW(),
                        updated_at = NOW()
                    """
                ),
                payload,
            )

            imported += 1

    return imported, errors


def import_fantasy_transactions(
    transactions_df: pd.DataFrame,
    source_file: str,
) -> tuple[int, list[str]]:
    errors: list[str] = []
    imported = 0

    required = {"transaction_id", "transaction_type"}
    errors.extend(
        validate_required_columns(transactions_df, "transactions", required)
    )

    if errors:
        return imported, errors

    with engine.begin() as conn:
        for index, row in transactions_df.iterrows():
            source_transaction_id = to_int(get_value(row, "transaction_id"))
            transaction_type = clean_text(get_value(row, "transaction_type"))

            if source_transaction_id is None or not transaction_type:
                errors.append(
                    f"transactions linha {index + 2}: "
                    "transaction_id ou transaction_type inválido."
                )
                continue

            payload = {
                "source_transaction_id": source_transaction_id,
                "transaction_type": transaction_type.upper(),
                "transaction_date": to_date(
                    get_value(row, "transaction_date")
                ),
                "season": clean_text(get_value(row, "season")),
                "from_team_id": to_int(get_value(row, "from_team_id")),
                "to_team_id": to_int(get_value(row, "to_team_id")),
                "initiated_by": clean_text(get_value(row, "initiated_by")),
                "status": clean_text(get_value(row, "status")),
                "notes": clean_text(get_value(row, "notes")),
                "source_file": source_file,
            }

            conn.execute(
                text(
                    """
                    INSERT INTO fantasy_transactions (
                        source_transaction_id,
                        transaction_type,
                        transaction_date,
                        season,
                        from_team_id,
                        to_team_id,
                        initiated_by,
                        status,
                        notes,
                        source_file,
                        source_sheet,
                        imported_at,
                        updated_at
                    )
                    VALUES (
                        :source_transaction_id,
                        :transaction_type,
                        :transaction_date,
                        :season,
                        :from_team_id,
                        :to_team_id,
                        :initiated_by,
                        :status,
                        :notes,
                        :source_file,
                        'transactions',
                        NOW(),
                        NOW()
                    )
                    ON CONFLICT (source_transaction_id)
                    DO UPDATE SET
                        transaction_type = EXCLUDED.transaction_type,
                        transaction_date = EXCLUDED.transaction_date,
                        season = EXCLUDED.season,
                        from_team_id = EXCLUDED.from_team_id,
                        to_team_id = EXCLUDED.to_team_id,
                        initiated_by = EXCLUDED.initiated_by,
                        status = EXCLUDED.status,
                        notes = EXCLUDED.notes,
                        source_file = EXCLUDED.source_file,
                        source_sheet = EXCLUDED.source_sheet,
                        imported_at = NOW(),
                        updated_at = NOW()
                    """
                ),
                payload,
            )

            imported += 1

    return imported, errors


def get_fantasy_transaction_id(
    conn,
    source_transaction_id: int,
) -> int | None:
    result = conn.execute(
        text(
            """
            SELECT fantasy_transaction_id
            FROM fantasy_transactions
            WHERE source_transaction_id = :source_transaction_id
            """
        ),
        {"source_transaction_id": source_transaction_id},
    ).scalar()

    return int(result) if result is not None else None


def import_fantasy_transaction_items(
    transaction_items_df: pd.DataFrame,
    source_file: str,
) -> tuple[int, list[str]]:
    errors: list[str] = []
    imported = 0

    required = {
        "transaction_id",
        "item_type",
        "asset_id",
    }
    errors.extend(
        validate_required_columns(
            transaction_items_df,
            "transactionitems",
            required,
        )
    )

    if errors:
        return imported, errors

    with engine.begin() as conn:
        # Evita duplicar os itens numa reimportação.
        conn.execute(text("DELETE FROM fantasy_transaction_items"))

        for index, row in transaction_items_df.iterrows():
            source_transaction_id = to_int(get_value(row, "transaction_id"))
            item_type = clean_text(get_value(row, "item_type"))
            asset_id = get_value(row, "asset_id")

            if source_transaction_id is None or not item_type:
                errors.append(
                    f"transactionitems linha {index + 2}: "
                    "transaction_id ou item_type inválido."
                )
                continue

            fantasy_transaction_id = get_fantasy_transaction_id(
                conn,
                source_transaction_id,
            )

            if fantasy_transaction_id is None:
                errors.append(
                    f"transactionitems linha {index + 2}: "
                    f"transaction_id {source_transaction_id} não encontrado "
                    "em fantasy_transactions."
                )
                continue

            item_type_normalized = item_type.lower().strip()

            player_source_id = None
            pick_source_id = None

            if item_type_normalized == "player":
                player_source_id = to_int(asset_id)

                if player_source_id is None:
                    errors.append(
                        f"transactionitems linha {index + 2}: "
                        "player asset_id inválido."
                    )
                    continue

            elif item_type_normalized == "pick":
                pick_source_id = normalize_pick_id(asset_id)

                if not pick_source_id:
                    errors.append(
                        f"transactionitems linha {index + 2}: "
                        "pick asset_id inválido."
                    )
                    continue

            else:
                errors.append(
                    f"transactionitems linha {index + 2}: "
                    f"item_type inválido ({item_type})."
                )
                continue

            payload = {
                "fantasy_transaction_id": fantasy_transaction_id,
                "source_item_id": to_int(get_value(row, "item_id")),
                "item_type": item_type_normalized,
                "player_source_id": player_source_id,
                "pick_source_id": pick_source_id,
                "from_team_id": to_int(get_value(row, "from_team_id")),
                "to_team_id": to_int(get_value(row, "to_team_id")),
                "from_roster_type": clean_text(
                    get_value(row, "from_roster_type")
                ),
                "to_roster_type": clean_text(
                    get_value(row, "to_roster_type")
                ),
                "effective_season": clean_text(
                    get_value(row, "effective_season")
                ),
                "item_notes": clean_text(get_value(row, "item_notes")),
                "source_file": source_file,
            }

            conn.execute(
                text(
                    """
                    INSERT INTO fantasy_transaction_items (
                        fantasy_transaction_id,
                        source_item_id,
                        item_type,
                        player_source_id,
                        pick_source_id,
                        from_team_id,
                        to_team_id,
                        from_roster_type,
                        to_roster_type,
                        effective_season,
                        item_notes,
                        source_file,
                        source_sheet,
                        imported_at,
                        updated_at
                    )
                    VALUES (
                        :fantasy_transaction_id,
                        :source_item_id,
                        :item_type,
                        :player_source_id,
                        :pick_source_id,
                        :from_team_id,
                        :to_team_id,
                        :from_roster_type,
                        :to_roster_type,
                        :effective_season,
                        :item_notes,
                        :source_file,
                        'transactionitems',
                        NOW(),
                        NOW()
                    )
                    """
                ),
                payload,
            )

            imported += 1

    return imported, errors


def import_fantasy_games(
    games_df: pd.DataFrame,
    source_file: str,
) -> tuple[int, list[str]]:
    errors: list[str] = []
    imported = 0

    required = {
        "id_jogo",
        "id_time_1",
        "nome_time_1",
        "pontos_time_1",
        "pontos_time_2",
        "id_time_2",
        "nome_time_2",
        "rodada",
    }
    errors.extend(validate_required_columns(games_df, "games", required))

    if errors:
        return imported, errors

    with engine.begin() as conn:
        for index, row in games_df.iterrows():
            source_game_id = to_int(get_value(row, "id_jogo"))
            team_1_id = to_int(get_value(row, "id_time_1"))
            team_2_id = to_int(get_value(row, "id_time_2"))

            if (
                source_game_id is None
                or team_1_id is None
                or team_2_id is None
                or team_1_id == team_2_id
            ):
                errors.append(
                    f"games linha {index + 2}: IDs de jogo/times inválidos."
                )
                continue

            payload = {
                "source_game_id": source_game_id,
                "team_1_id": team_1_id,
                "team_1_name": clean_text(get_value(row, "nome_time_1")),
                "team_1_points": to_float(get_value(row, "pontos_time_1")),
                "team_2_points": to_float(get_value(row, "pontos_time_2")),
                "team_2_id": team_2_id,
                "team_2_name": clean_text(get_value(row, "nome_time_2")),
                "round": to_int(get_value(row, "rodada")),
                "source_file": source_file,
            }

            conn.execute(
                text(
                    """
                    INSERT INTO fantasy_games (
                        source_game_id,
                        team_1_id,
                        team_1_name,
                        team_1_points,
                        team_2_points,
                        team_2_id,
                        team_2_name,
                        round,
                        source_file,
                        source_sheet,
                        imported_at,
                        updated_at
                    )
                    VALUES (
                        :source_game_id,
                        :team_1_id,
                        :team_1_name,
                        :team_1_points,
                        :team_2_points,
                        :team_2_id,
                        :team_2_name,
                        :round,
                        :source_file,
                        'games',
                        NOW(),
                        NOW()
                    )
                    ON CONFLICT (source_game_id)
                    DO UPDATE SET
                        team_1_id = EXCLUDED.team_1_id,
                        team_1_name = EXCLUDED.team_1_name,
                        team_1_points = EXCLUDED.team_1_points,
                        team_2_points = EXCLUDED.team_2_points,
                        team_2_id = EXCLUDED.team_2_id,
                        team_2_name = EXCLUDED.team_2_name,
                        round = EXCLUDED.round,
                        source_file = EXCLUDED.source_file,
                        source_sheet = EXCLUDED.source_sheet,
                        imported_at = NOW(),
                        updated_at = NOW()
                    """
                ),
                payload,
            )

            imported += 1

    return imported, errors


def import_fantasy_schedule(
    schedule_df: pd.DataFrame,
    source_file: str,
) -> tuple[int, list[str]]:
    errors: list[str] = []
    imported = 0

    required = {
        "semana_num",
        "team_abbr",
        "jogo_na_semana",
        "game_date",
    }
    errors.extend(validate_required_columns(schedule_df, "Semana", required))

    if errors:
        return imported, errors

    with engine.begin() as conn:
        for index, row in schedule_df.iterrows():
            week_number = to_int(get_value(row, "semana_num"))
            nba_team_abbr = clean_text(get_value(row, "team_abbr"))
            game_number_in_week = to_int(get_value(row, "jogo_na_semana"))
            game_date = to_date(get_value(row, "game_date"))

            if (
                week_number is None
                or not nba_team_abbr
                or game_number_in_week is None
                or game_date is None
            ):
                errors.append(
                    f"Semana linha {index + 2}: dados obrigatórios inválidos."
                )
                continue

            payload = {
                "week_number": week_number,
                "week_start": to_date(get_value(row, "semana_inicio")),
                "nba_team_abbr": nba_team_abbr.upper(),
                "nba_team_name": clean_text(get_value(row, "team_name")),
                "game_number_in_week": game_number_in_week,
                "game_date": game_date,
                "nba_game_id": to_int(get_value(row, "game_id")),
                "opponent_abbr": clean_text(
                    get_value(row, "opponent_abbr")
                ),
                "opponent_name": clean_text(
                    get_value(row, "opponent_name")
                ),
                "home_away": clean_text(get_value(row, "home_away")),
                "source_file": source_file,
            }

            conn.execute(
                text(
                    """
                    INSERT INTO fantasy_schedule (
                        week_number,
                        week_start,
                        nba_team_abbr,
                        nba_team_name,
                        game_number_in_week,
                        game_date,
                        nba_game_id,
                        opponent_abbr,
                        opponent_name,
                        home_away,
                        source_file,
                        source_sheet,
                        imported_at,
                        updated_at
                    )
                    VALUES (
                        :week_number,
                        :week_start,
                        :nba_team_abbr,
                        :nba_team_name,
                        :game_number_in_week,
                        :game_date,
                        :nba_game_id,
                        :opponent_abbr,
                        :opponent_name,
                        :home_away,
                        :source_file,
                        'Semana',
                        NOW(),
                        NOW()
                    )
                    ON CONFLICT (
                        week_number,
                        nba_team_abbr,
                        game_number_in_week,
                        game_date,
                        nba_game_id
                    )
                    DO UPDATE SET
                        week_start = EXCLUDED.week_start,
                        nba_team_name = EXCLUDED.nba_team_name,
                        opponent_abbr = EXCLUDED.opponent_abbr,
                        opponent_name = EXCLUDED.opponent_name,
                        home_away = EXCLUDED.home_away,
                        source_file = EXCLUDED.source_file,
                        source_sheet = EXCLUDED.source_sheet,
                        imported_at = NOW(),
                        updated_at = NOW()
                    """
                ),
                payload,
            )

            imported += 1

    return imported, errors


def db_count(table_name: str) -> int:
    with engine.begin() as conn:
        value = conn.execute(
            text(f"SELECT COUNT(*) FROM {table_name}")
        ).scalar()

    return int(value or 0)


def main():
    print("=" * 72)
    print("PNBC-02 — Carga Inicial do roster.xlsx para o Neon")
    print("=" * 72)

    if not is_postgres_v5():
        raise RuntimeError(
            "O banco atual não é PostgreSQL. "
            "Confirme DATABASE_URL/secrets para apontar para o Neon."
        )

    if not WORKBOOK_PATH.exists():
        raise FileNotFoundError(
            f"Arquivo não encontrado: {WORKBOOK_PATH}"
        )

    healthcheck_db_v5()

    workbook = pd.ExcelFile(WORKBOOK_PATH)

    print(f"Arquivo: {WORKBOOK_PATH}")
    print(f"Abas encontradas: {', '.join(workbook.sheet_names)}")
    print()

    data = {
        sheet_key: read_sheet(workbook, sheet_name)
        for sheet_key, sheet_name in SHEET_ALIASES.items()
    }

    summary: list[tuple[str, int, list[str]]] = []

    # Ordem obrigatória por dependência de chaves estrangeiras.
    summary.append(
        ("teams", *ensure_fantasy_teams(data["teams"], SOURCE_FILE_NAME))
    )
    summary.append(
        (
            "fantasy_players",
            *import_fantasy_players(data["players"], SOURCE_FILE_NAME),
        )
    )
    summary.append(
        (
            "fantasy_roster",
            *import_fantasy_roster(data["roster"], SOURCE_FILE_NAME),
        )
    )
    summary.append(
        (
            "fantasy_development",
            *import_fantasy_development(
                data["development"],
                SOURCE_FILE_NAME,
            ),
        )
    )
    summary.append(
        (
            "fantasy_fines",
            *import_fantasy_fines(data["fines"], SOURCE_FILE_NAME),
        )
    )
    summary.append(
        (
            "fantasy_picks",
            *import_fantasy_picks(data["picks"], SOURCE_FILE_NAME),
        )
    )
    summary.append(
        (
            "fantasy_transactions",
            *import_fantasy_transactions(
                data["transactions"],
                SOURCE_FILE_NAME,
            ),
        )
    )
    summary.append(
        (
            "fantasy_transaction_items",
            *import_fantasy_transaction_items(
                data["transactionitems"],
                SOURCE_FILE_NAME,
            ),
        )
    )
    summary.append(
        (
            "fantasy_games",
            *import_fantasy_games(data["games"], SOURCE_FILE_NAME),
        )
    )
    summary.append(
        (
            "fantasy_schedule",
            *import_fantasy_schedule(data["Semana"], SOURCE_FILE_NAME),
        )
    )

    print()
    print("=" * 72)
    print("RESUMO DA IMPORTAÇÃO")
    print("=" * 72)

    total_errors = 0

    for target_name, imported, errors in summary:
        print(f"{target_name}: {imported} registros processados")

        if errors:
            total_errors += len(errors)
            print(f"  Avisos/erros: {len(errors)}")

            for error in errors[:15]:
                print(f"  - {error}")

            if len(errors) > 15:
                print(
                    f"  - ... e mais {len(errors) - 15} aviso(s)/erro(s)."
                )

    print()
    print("=" * 72)
    print("CONTAGEM ATUAL NO NEON")
    print("=" * 72)

    tables = [
        "teams",
        "fantasy_players",
        "fantasy_roster",
        "fantasy_development",
        "fantasy_fines",
        "fantasy_picks",
        "fantasy_transactions",
        "fantasy_transaction_items",
        "fantasy_games",
        "fantasy_schedule",
    ]

    for table_name in tables:
        try:
            print(f"{table_name}: {db_count(table_name)}")
        except Exception as exc:
            print(f"{table_name}: erro ao consultar ({exc})")

    print()
    print("=" * 72)

    if total_errors:
        print(
            f"Importação concluída com {total_errors} aviso(s)/erro(s). "
            "Leia o relatório acima antes de alterar as páginas."
        )
    else:
        print(
            "Importação concluída sem erros de validação."
        )

    print("=" * 72)


if __name__ == "__main__":
    main()