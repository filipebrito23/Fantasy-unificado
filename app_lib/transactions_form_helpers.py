from __future__ import annotations

from typing import Any

import pandas as pd

from app_lib.excel_utils import get_next_id
from app_lib.transactions_service import pick_domain_ids


def get_transaction_default_team_options(teams: pd.DataFrame) -> list[str]:
    if teams.empty or "team_name" not in teams.columns:
        return []
    return teams["team_name"].tolist()


def get_team_id_map(teams: pd.DataFrame) -> dict[str, int]:
    if teams.empty or "team_name" not in teams.columns or "team_id" not in teams.columns:
        return {}
    return dict(zip(teams["team_name"], teams["team_id"]))


def get_player_labels(player_lookup: dict[int, str], player_ids: list[int]) -> dict[int, str]:
    return {int(pid): player_lookup.get(int(pid), str(pid)) for pid in player_ids}


def get_player_ids_from_team(source_df: pd.DataFrame) -> list[int]:
    if source_df.empty or "player_id" not in source_df.columns:
        return []
    return (
        pd.to_numeric(source_df["player_id"], errors="coerce")
        .dropna()
        .astype(int)
        .tolist()
    )


def collect_valid_item_rows(all_item_rows: list[dict[str, Any]]) -> tuple[list[dict[str, Any]], list[str]]:
    valid_item_rows: list[dict[str, Any]] = []
    errors: list[str] = []
    for idx, row in enumerate(all_item_rows, start=1):
        if row["asset_id"] in [None, "", "Sem jogadores disponíveis", "Sem picks disponíveis"]:
            errors.append(f"Item {idx}: asset inválido.")
        else:
            valid_item_rows.append(row)
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

    if tx_type == "TRADE":
        if from_team_id is None or to_team_id is None:
            errors.append("TRADE exige Time A e Time B.")
        elif from_team_id == to_team_id:
            errors.append("TRADE exige times diferentes.")

    if tx_type == "MOVE":
        if from_team_id is None:
            errors.append("MOVE exige Time A.")
        if any(
            str(row.get("from_roster_type", "")).upper() == str(row.get("to_roster_type", "")).upper()
            for row in valid_item_rows
            if row.get("item_type") == "player"
        ):
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
        type_col: tx_type,
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
    item_id_col = (
        "item_id"
        if (not transaction_items_df.empty and "item_id" in transaction_items_df.columns)
        else "itemid"
    )
    transaction_id_col = (
        "transaction_id"
        if (not transaction_items_df.empty and "transaction_id" in transaction_items_df.columns)
        else "transactionid"
    )
    item_type_col = (
        "item_type"
        if (not transaction_items_df.empty and "item_type" in transaction_items_df.columns)
        else "itemtype"
    )
    asset_id_col = (
        "asset_id"
        if (not transaction_items_df.empty and "asset_id" in transaction_items_df.columns)
        else "assetid"
    )
    from_rt_col = (
        "from_roster_type"
        if (not transaction_items_df.empty and "from_roster_type" in transaction_items_df.columns)
        else "fromrostertype"
    )
    to_rt_col = (
        "to_roster_type"
        if (not transaction_items_df.empty and "to_roster_type" in transaction_items_df.columns)
        else "torostertype"
    )
    from_team_col = (
        "from_team_id"
        if (not transaction_items_df.empty and "from_team_id" in transaction_items_df.columns)
        else "fromteamid"
    )
    to_team_col = (
        "to_team_id"
        if (not transaction_items_df.empty and "to_team_id" in transaction_items_df.columns)
        else "toteamid"
    )

    prepared_items: list[dict[str, Any]] = []
    for row in valid_item_rows:
        prepared_items.append(
            {
                transaction_id_col: next_tx_id,
                item_id_col: row["item_id"],
                item_type_col: row["item_type"],
                asset_id_col: row["asset_id"],
                from_rt_col: row["from_roster_type"],
                to_rt_col: row["to_roster_type"],
                from_team_col: row["from_team_id"],
                to_team_col: row["to_team_id"],
            }
        )
    return prepared_items


def normalize_transaction_display_df(df: pd.DataFrame) -> pd.DataFrame:
    display_df = df.copy()
    object_like_id_cols = [
        "transaction_id",
        "transactionid",
        "item_id",
        "itemid",
        "from_team_id",
        "fromteamid",
        "to_team_id",
        "toteamid",
        "asset_id",
        "assetid",
    ]
    for col in object_like_id_cols:
        if col in display_df.columns:
            display_df[col] = display_df[col].fillna("").astype(str)
    return display_df


def make_next_transaction_id(tx_base_df: pd.DataFrame, start: int = 1) -> tuple[Any, str]:
    tx_id_col = "transaction_id" if "transaction_id" in tx_base_df.columns else "transactionid"
    next_id = get_next_id(tx_base_df, tx_id_col, start=start)
    return next_id, tx_id_col


def get_pick_domain_ids_for_team(data: dict[str, pd.DataFrame], team_id: int | None) -> list[Any]:
    if team_id is None:
        return []
    return sorted(pick_domain_ids(data, team_id))