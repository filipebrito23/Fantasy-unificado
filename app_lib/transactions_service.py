import pandas as pd
from openpyxl import load_workbook

from app_lib.excel_utils import load_sheet_df, save_sheet_df, ensure_unique_columns

TX_SHEET = "transactions"
TX_ITEMS_SHEET = "transactionitems"


def roster_domain_ids(data, team_id: int, roster_type: str | None = None) -> set:
    ids = set()

    sheet_names = ["roster", "development"]
    if roster_type == "MAIN":
        sheet_names = ["roster"]
    elif roster_type == "DEV":
        sheet_names = ["development"]

    for sheet in sheet_names:
        df = data.get(sheet, pd.DataFrame())
        if df.empty or not {"team_id", "player_id"}.issubset(df.columns):
            continue

        team_ids = pd.to_numeric(df["team_id"], errors="coerce")
        player_ids = pd.to_numeric(df["player_id"], errors="coerce")

        mask = team_ids.eq(team_id) & player_ids.notna()
        ids |= set(player_ids.loc[mask].astype(int).tolist())

    return ids


def pick_domain_ids(data, team_id: int) -> set:
    picks = data.get("picks", pd.DataFrame())
    if picks.empty:
        return set()

    owner_cols = [c for c in picks.columns if "owner" in c.lower() or "team" in c.lower()]
    if not owner_cols:
        return set()

    owner_col = owner_cols[0]
    id_col = picks.columns[0]

    owner_ids = pd.to_numeric(picks[owner_col], errors="coerce")
    valid_mask = owner_ids.notna() & owner_ids.eq(team_id)

    return set(
        picks.loc[valid_mask, id_col]
        .dropna()
        .astype(str)
        .tolist()
    )


def validate_items(data, from_team_id: int, item_rows: list[dict]) -> list[str]:
    errors = []

    for i, item in enumerate(item_rows, start=1):
        item_type = str(item.get("item_type", "")).strip().lower()
        asset_id = item.get("asset_id")
        from_roster_type = item.get("from_roster_type")

        player_ids = roster_domain_ids(data, from_team_id, from_roster_type)
        pick_ids = pick_domain_ids(data, from_team_id)

        if item_type == "player":
            try:
                asset_id_int = int(asset_id)
            except Exception:
                asset_id_int = None

            if asset_id_int is None or asset_id_int not in player_ids:
                errors.append(f"Item {i}: jogador fora do domínio do time origem.")

        if item_type == "pick":
            if str(asset_id) not in pick_ids:
                errors.append(f"Item {i}: pick fora do domínio do time origem.")

    return errors


def validate_items_bilateral(data, item_rows: list[dict]) -> list[str]:
    errors = []

    for i, item in enumerate(item_rows, start=1):
        item_type = str(item.get("item_type", item.get("itemtype", ""))).strip().lower()
        asset_id = item.get("asset_id", item.get("assetid"))
        from_team_id = item.get("from_team_id", item.get("fromteamid"))
        to_team_id = item.get("to_team_id", item.get("toteamid"))
        from_roster_type = str(item.get("from_roster_type", item.get("fromrostertype", ""))).strip().upper()
        to_roster_type = str(item.get("to_roster_type", item.get("torostertype", ""))).strip().upper()

        if from_team_id is None:
            errors.append(f"Item {i}: sem time de origem.")
            continue

        try:
            from_team_id = int(from_team_id)
        except Exception:
            errors.append(f"Item {i}: time de origem inválido.")
            continue

        try:
            to_team_id = int(to_team_id) if to_team_id is not None else None
        except Exception:
            to_team_id = None

        same_team = to_team_id is not None and from_team_id == to_team_id

        if item_type == "player":
            try:
                asset_id_int = int(asset_id)
            except Exception:
                errors.append(f"Item {i}: jogador inválido.")
                continue

            player_ids = roster_domain_ids(data, from_team_id, from_roster_type)
            if asset_id_int not in player_ids:
                errors.append(f"Item {i}: jogador fora do domínio do time origem.")
                continue

            if same_team:
                if from_roster_type not in {"MAIN", "DEV"} or to_roster_type not in {"MAIN", "DEV"}:
                    errors.append(f"Item {i}: movimentação interna exige MAIN/DEV válidos.")
                elif from_roster_type == to_roster_type:
                    errors.append(f"Item {i}: movimentação interna deve trocar entre MAIN e DEV.")

        elif item_type == "pick":
            pick_ids = pick_domain_ids(data, from_team_id)
            if str(asset_id) not in pick_ids:
                errors.append(f"Item {i}: pick fora do domínio do time origem.")

            if same_team:
                errors.append(f"Item {i}: pick não pode ser movimentada dentro do mesmo time.")

        else:
            errors.append(f"Item {i}: tipo de asset inválido.")

    return errors


def append_transaction(file_path: str, tx_row: dict, item_rows: list[dict]):
    wb = load_workbook(file_path)

    tx_df = ensure_unique_columns(load_sheet_df(wb, TX_SHEET))
    items_df = ensure_unique_columns(load_sheet_df(wb, TX_ITEMS_SHEET))

    if tx_df.empty and TX_SHEET not in wb.sheetnames:
        tx_df = pd.DataFrame(columns=list(tx_row.keys()))

    if items_df.empty and TX_ITEMS_SHEET not in wb.sheetnames and item_rows:
        items_df = pd.DataFrame(columns=list(item_rows[0].keys()))

    new_tx_df = ensure_unique_columns(pd.DataFrame([tx_row]))
    tx_df = pd.concat([tx_df, new_tx_df], ignore_index=True)

    if item_rows:
        new_items_df = ensure_unique_columns(pd.DataFrame(item_rows))
        items_df = pd.concat([items_df, new_items_df], ignore_index=True)

    save_sheet_df(wb, TX_SHEET, tx_df)
    if item_rows:
        save_sheet_df(wb, TX_ITEMS_SHEET, items_df)

    wb.save(file_path)


def update_rosters(file_path: str, tx_row: dict, item_rows: list[dict]):
    wb = load_workbook(file_path)

    roster_df = load_sheet_df(wb, "roster")
    dev_df = load_sheet_df(wb, "development")
    picks_df = load_sheet_df(wb, "picks")

    from_team_raw = tx_row.get("from_team_id", tx_row.get("fromteamid"))
    to_team_raw = tx_row.get("to_team_id", tx_row.get("toteamid"))

    from_team_id = int(from_team_raw)
    to_team_id = int(to_team_raw)

    def num(series):
        return pd.to_numeric(series, errors="coerce")

    for item in item_rows:
        item_type = str(item.get("item_type", item.get("itemtype", ""))).strip().lower()
        asset_id = item.get("asset_id", item.get("assetid"))
        item_from_team = int(item.get("from_team_id", item.get("fromteamid", from_team_id)))
        item_to_team = int(item.get("to_team_id", item.get("toteamid", to_team_id)))

        if item_type == "player":
            pid = int(asset_id)
            from_rt = str(item.get("from_roster_type", item.get("fromrostertype", ""))).strip().upper()
            to_rt = str(item.get("to_roster_type", item.get("torostertype", ""))).strip().upper()

            if from_rt not in {"MAIN", "DEV"} or to_rt not in {"MAIN", "DEV"}:
                continue

            source_df = roster_df if from_rt == "MAIN" else dev_df
            target_df = roster_df if to_rt == "MAIN" else dev_df

            if source_df.empty or "team_id" not in source_df.columns or "player_id" not in source_df.columns:
                continue

            source_team_ids = num(source_df["team_id"])
            source_player_ids = num(source_df["player_id"])

            source_mask = source_team_ids.eq(item_from_team) & source_player_ids.eq(pid)

            if not source_mask.any():
                continue

            moving_rows = source_df.loc[source_mask].copy()
            source_df = source_df.loc[~source_mask].copy()
            moving_rows.loc[:, "team_id"] = item_to_team

            target_df = pd.concat([target_df, moving_rows], ignore_index=True)

            if from_rt == "MAIN":
                roster_df = source_df
            else:
                dev_df = source_df

            if to_rt == "MAIN":
                roster_df = target_df
            else:
                dev_df = target_df

        elif item_type == "pick" and not picks_df.empty:
            id_col = picks_df.columns[0]
            owner_cols = [c for c in picks_df.columns if "owner" in c.lower() or "team" in c.lower()]
            if owner_cols:
                owner_col = owner_cols[0]
                owner_ids = pd.to_numeric(picks_df[owner_col], errors="coerce")
                mask = picks_df[id_col].astype(str).eq(str(asset_id)) & owner_ids.eq(item_from_team)
                picks_df.loc[mask, owner_col] = item_to_team

    save_sheet_df(wb, "roster", roster_df)
    save_sheet_df(wb, "development", dev_df)
    save_sheet_df(wb, "picks", picks_df)

    wb.save(file_path)


def compact_columns(df: pd.DataFrame) -> pd.DataFrame:
    out = df.copy()
    out.columns = [
        str(c).strip().lower().replace("_", "").replace(" ", "")
        for c in out.columns
    ]
    return out


def build_transactions_history(
    tx_df: pd.DataFrame,
    items_df: pd.DataFrame,
    selected_team_id: int,
    team_lookup: dict,
    player_lookup: dict,
) -> pd.DataFrame:
    if tx_df is None or tx_df.empty:
        return pd.DataFrame()

    tx = compact_columns(tx_df)

    items = items_df.copy() if items_df is not None else pd.DataFrame()
    if not items.empty:
        items = compact_columns(items)

    if not {"fromteamid", "toteamid"}.issubset(tx.columns):
        return pd.DataFrame()

    team_mask = (
        tx["fromteamid"].astype(str).eq(str(selected_team_id))
        | tx["toteamid"].astype(str).eq(str(selected_team_id))
    )
    tx = tx.loc[team_mask].copy()

    if tx.empty:
        return pd.DataFrame()

    tx["from_team"] = tx["fromteamid"].map(team_lookup).fillna(tx["fromteamid"])
    tx["to_team"] = tx["toteamid"].map(team_lookup).fillna(tx["toteamid"])

    if items.empty or "transactionid" not in items.columns:
        tx["items_summary"] = "-"
    else:
        items = items.loc[
            items["transactionid"].astype(str).isin(tx["transactionid"].astype(str))
        ].copy()

        def describe_item(row):
            item_type = str(row.get("itemtype", "")).upper()
            asset_id = row.get("assetid")

            if item_type == "PLAYER":
                try:
                    pid = int(asset_id)
                except Exception:
                    pid = asset_id
                asset_label = player_lookup.get(pid, asset_id)
            else:
                asset_label = asset_id

            from_rt = row.get("fromrostertype")
            to_rt = row.get("torostertype")

            roster_part = ""
            if pd.notna(from_rt) or pd.notna(to_rt):
                roster_part = f" ({from_rt or '-'} → {to_rt or '-'})"

            return f"{item_type}: {asset_label}{roster_part}"

        if not items.empty:
            items["item_desc"] = items.apply(describe_item, axis=1)
            items_grouped = (
                items.groupby("transactionid")["item_desc"]
                .apply(lambda s: " | ".join(s.astype(str)))
                .reset_index()
            )
            tx = tx.merge(items_grouped, on="transactionid", how="left")
            tx = tx.rename(columns={"item_desc": "items_summary"})
        else:
            tx["items_summary"] = "-"

    tx = tx.rename(columns={
        "transactionid": "transaction_id",
        "transactiontype": "transaction_type",
        "transactiondate": "transaction_date",
        "initiatedby": "initiated_by",
    })

    preferred_cols = [
        "transaction_id",
        "transaction_date",
        "transaction_type",
        "season",
        "from_team",
        "to_team",
        "initiated_by",
        "status",
        "items_summary",
        "notes",
    ]
    existing_cols = [c for c in preferred_cols if c in tx.columns]

    sort_cols = [c for c in ["transaction_date", "transaction_id"] if c in tx.columns]
    if sort_cols:
        tx = tx.sort_values(by=sort_cols, ascending=False)

    return tx[existing_cols]