from __future__ import annotations

from typing import Any

import pandas as pd

from app_lib.excel_utils import get_next_id
from app_lib.fantasy_data_service import get_neon_connection
from app_lib.transactions_service import (
    _db_roster_type,
)
from sqlalchemy import text


def _v(row: dict[str, Any], *keys, default=None):
    for k in keys:
        if k in row and row.get(k) not in [None, ""]:
            return row.get(k)
    return default


def get_transaction_default_team_options(teams: pd.DataFrame) -> list[str]:
    if teams.empty or "team_name" not in teams.columns:
        return []
    return teams["team_name"].tolist()


def get_team_id_map(teams: pd.DataFrame) -> dict[str, int]:
    if teams.empty or "team_name" not in teams.columns or "team_id" not in teams.columns:
        return {}
    return dict(zip(teams["team_name"], teams["team_id"]))

def get_active_team_players(
    team_id: int | None,
    roster_type: str | None,
) -> list[dict[str, Any]]:
    """
    Retorna os jogadores ativos do Neon para montar selectboxes.

    asset_id sempre corresponde a source_player_id, que é o mesmo
    identificador usado em fantasy_roster_seasons e transactions.
    """
    if team_id is None:
        return []

    db_roster_type = _db_roster_type(
        roster_type
    )

    if db_roster_type is None:
        return []

    with get_neon_connection() as conn:
        result = conn.execute(
            text(
                """
                SELECT DISTINCT ON (
                    frs.source_player_id
                )
                    frs.source_player_id,
                    fp.player_name,
                    fp.position,
                    frs.roster_type
                FROM fantasy_roster_seasons frs
                JOIN fantasy_players fp
                    ON fp.source_player_id =
                       frs.source_player_id
                WHERE frs.team_id = :team_id
                  AND LOWER(frs.roster_type) =
                      LOWER(:roster_type)
                  AND frs.is_active = TRUE
                ORDER BY
                    frs.source_player_id,
                    frs.season,
                    fp.player_name
                """
            ),
            {
                "team_id": int(team_id),
                "roster_type": db_roster_type,
            },
        )

        return [
            {
                "asset_id": int(
                    row.source_player_id
                ),
                "label": (
                    f"{row.player_name} "
                    f"({row.position or '-'})"
                ),
                "player_name": row.player_name,
                "position": row.position,
                "roster_type": row.roster_type,
            }
            for row in result.fetchall()
        ]

def get_active_team_picks(
    team_id: int | None,
) -> list[dict[str, Any]]:
    """
    Retorna picks atualmente pertencentes ao time no Neon.

    asset_id é source_pick_id, pois é esse identificador que
    _swap_pick_owner() usa ao atualizar fantasy_picks.
    """
    if team_id is None:
        return []

    with get_neon_connection() as conn:
        result = conn.execute(
            text(
                """
                SELECT
                    fp.source_pick_id,
                    fp.year,
                    fp.round,
                    original_team.team_name AS original_team_name
                FROM fantasy_picks fp
                LEFT JOIN teams original_team
                    ON original_team.team_id =
                       fp.original_team_pick_id
                WHERE fp.current_team_owner_id =
                      :team_id
                ORDER BY
                    fp.year,
                    fp.round,
                    fp.source_pick_id
                """
            ),
            {
                "team_id": int(team_id),
            },
        )

        rows = []

        for row in result.fetchall():
            source_pick_id = str(
                row.source_pick_id
            ).strip()

            original_team = (
                row.original_team_name
                or "Time original desconhecido"
            )

            rows.append(
                {
                    "asset_id": source_pick_id,
                    "label": (
                        f"{row.year} - Round {row.round} "
                        f"- {original_team}"
                    ),
                    "year": row.year,
                    "round": row.round,
                    "original_team_name": (
                        original_team
                    ),
                }
            )

        return rows

def collect_valid_item_rows(all_item_rows: list[dict[str, Any]]) -> tuple[list[dict[str, Any]], list[str]]:
    valid_item_rows: list[dict[str, Any]] = []
    errors: list[str] = []
    for idx, row in enumerate(all_item_rows, start=1):
        asset = _v(row, "asset_id", "assetid")
        if asset in [None, "", "Sem jogadores disponíveis", "Sem picks disponíveis"]:
            errors.append(f"Item {idx}: asset inválido.")
            continue
        item_type = str(_v(row, "item_type", "itemtype", default="")).strip().lower()
        from_team_id = _v(row, "from_team_id", "fromteamid")
        to_team_id = _v(row, "to_team_id", "toteamid")
        from_rt = str(_v(row, "from_roster_type", "fromrostertype", default="")).strip().upper() or None
        to_rt = str(_v(row, "to_roster_type", "torostertype", default="")).strip().upper() or None
        valid_item_rows.append({
            "item_id": _v(row, "item_id", "itemid", default=idx),
            "item_type": item_type,
            "asset_id": asset,
            "from_team_id": from_team_id,
            "to_team_id": to_team_id,
            "from_roster_type": from_rt,
            "to_roster_type": to_rt,
        })
    if not valid_item_rows:
        errors.append("A transaction precisa ter ao menos um asset válido.")
    return valid_item_rows, errors


def validate_transaction_form(
    tx_type: str,
    from_team_id: int | None,
    to_team_id: int | None,
    valid_item_rows: list[dict[str, Any]],
) -> list[str]:
    errors: list[str] = []
    tx_type = str(tx_type or "").strip().upper()
    has_player = any(row.get("item_type") == "player" for row in valid_item_rows)

    if tx_type == "TRADE":
        if from_team_id is None or to_team_id is None:
            errors.append("TRADE exige Time A e Time B.")
        elif from_team_id == to_team_id:
            errors.append("TRADE exige times diferentes.")

    if tx_type == "MOVE":
        if from_team_id is None:
            errors.append("MOVE exige Time A.")
        if has_player and any(str(row.get("from_roster_type", "")).upper() == str(row.get("to_roster_type", "")).upper() for row in valid_item_rows if row.get("item_type") == "player"):
            errors.append("MOVE exige troca entre MAIN e DEV.")

    if tx_type == "WAIVE" and to_team_id is not None:
        errors.append("WAIVE não usa Time B.")

    if tx_type == "ADD" and from_team_id is not None:
        errors.append("ADD não usa Time A.")

    return errors


def build_tx_row(
    tx_base_df: pd.DataFrame,
    next_tx_id: Any,
    tx_date: Any,
    tx_type: str,
    tx_season: str,
    from_team_id: int | None,
    to_team_id: int | None,
    initiated_by: str,
    tx_status: str,
    tx_notes: str,
) -> dict[str, Any]:
    tx_id_col = "transaction_id" if "transaction_id" in tx_base_df.columns else "transactionid"
    date_col = "transaction_date" if "transaction_date" in tx_base_df.columns else "transactiondate"
    type_col = "transaction_type" if "transaction_type" in tx_base_df.columns else "transactiontype"
    from_col = "from_team_id" if "from_team_id" in tx_base_df.columns else "fromteamid"
    to_col = "to_team_id" if "to_team_id" in tx_base_df.columns else "toteamid"
    initiated_col = "initiated_by" if "initiated_by" in tx_base_df.columns else "initiatedby"
    return {
        tx_id_col: next_tx_id,
        date_col: str(tx_date),
        type_col: str(tx_type).strip().upper(),
        "season": tx_season,
        from_col: from_team_id,
        to_col: to_team_id,
        initiated_col: initiated_by,
        "status": tx_status,
        "notes": tx_notes,
    }


def build_prepared_items(
    transaction_items_df: pd.DataFrame,
    next_tx_id: Any,
    valid_item_rows: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    item_id_col = "item_id" if (not transaction_items_df.empty and "item_id" in transaction_items_df.columns) else "itemid"
    transaction_id_col = "transaction_id" if (not transaction_items_df.empty and "transaction_id" in transaction_items_df.columns) else "transactionid"
    item_type_col = "item_type" if (not transaction_items_df.empty and "item_type" in transaction_items_df.columns) else "itemtype"
    asset_id_col = "asset_id" if (not transaction_items_df.empty and "asset_id" in transaction_items_df.columns) else "assetid"
    from_rt_col = "from_roster_type" if (not transaction_items_df.empty and "from_roster_type" in transaction_items_df.columns) else "fromrostertype"
    to_rt_col = "to_roster_type" if (not transaction_items_df.empty and "to_roster_type" in transaction_items_df.columns) else "torostertype"
    from_team_col = "from_team_id" if (not transaction_items_df.empty and "from_team_id" in transaction_items_df.columns) else "fromteamid"
    to_team_col = "to_team_id" if (not transaction_items_df.empty and "to_team_id" in transaction_items_df.columns) else "toteamid"

    prepared_items: list[dict[str, Any]] = []
    for row in valid_item_rows:
        prepared_items.append(
            {
                transaction_id_col: next_tx_id,
                item_id_col: row.get("item_id"),
                item_type_col: row.get("item_type"),
                asset_id_col: row.get("asset_id"),
                from_rt_col: row.get("from_roster_type"),
                to_rt_col: row.get("to_roster_type"),
                from_team_col: row.get("from_team_id"),
                to_team_col: row.get("to_team_id"),
            }
        )
    return prepared_items


def normalize_transaction_display_df(df: pd.DataFrame) -> pd.DataFrame:
    display_df = df.copy()
    object_like_id_cols = ["transaction_id", "transactionid", "item_id", "itemid", "from_team_id", "fromteamid", "to_team_id", "toteamid", "asset_id", "assetid"]
    for col in object_like_id_cols:
        if col in display_df.columns:
            display_df[col] = display_df[col].fillna("").astype(str)
    return display_df


def make_next_transaction_id(tx_base_df: pd.DataFrame, start: int = 1) -> tuple[Any, str]:
    tx_id_col = "transaction_id" if "transaction_id" in tx_base_df.columns else "transactionid"
    next_id = get_next_id(tx_base_df, tx_id_col, start=start)
    return next_id, tx_id_col

