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


def validate_items_bilateral(data, item_rows: list[dict], transaction_type: str | None = None) -> list[str]:
    errors = []
    tx_type = str(transaction_type or "").strip().upper()

    for i, item in enumerate(item_rows, start=1):
        item_type = str(item.get("item_type", item.get("itemtype", ""))).strip().lower()
        asset_id = item.get("asset_id", item.get("assetid"))
        from_team_id = item.get("from_team_id", item.get("fromteamid"))
        to_team_id = item.get("to_team_id", item.get("toteamid"))
        from_roster_type = str(item.get("from_roster_type", item.get("fromrostertype", ""))).strip().upper()
        to_roster_type = str(item.get("to_roster_type", item.get("torostertype", ""))).strip().upper()

        try:
            from_team_id = int(from_team_id) if from_team_id is not None and str(from_team_id).strip() != "" else None
        except Exception:
            errors.append(f"Item {i}: time de origem inválido.")
            continue

        try:
            to_team_id = int(to_team_id) if to_team_id is not None and str(to_team_id).strip() != "" else None
        except Exception:
            errors.append(f"Item {i}: time de destino inválido.")
            continue

        if tx_type == "TRADE":
            if from_team_id is None or to_team_id is None:
                errors.append(f"Item {i}: trade exige time de origem e destino.")
                continue

        elif tx_type in {"WAIVE", "DISPENSA", "DISMISS", "DROP"}:
            if from_team_id is None:
                errors.append(f"Item {i}: dispensa exige time de origem.")
                continue

        elif tx_type in {"ADD", "SIGN", "ASSINATURA"}:
            if to_team_id is None:
                errors.append(f"Item {i}: adição exige time de destino.")
                continue

        elif tx_type in {"MOVE", "CALLUP", "SENDDOWN", "PROMOTION"}:
            if from_team_id is None or to_team_id is None:
                errors.append(f"Item {i}: movimentação interna exige origem e destino.")
                continue

        same_team = (
            from_team_id is not None and
            to_team_id is not None and
            from_team_id == to_team_id
        )

        if item_type == "player":
            try:
                asset_id_int = int(asset_id)
            except Exception:
                errors.append(f"Item {i}: jogador inválido.")
                continue

            if from_team_id is not None:
                player_ids = roster_domain_ids(data, from_team_id, from_roster_type)
                if asset_id_int not in player_ids:
                    errors.append(f"Item {i}: jogador fora do domínio do time origem.")
                    continue

            if tx_type in {"MOVE", "CALLUP", "SENDDOWN", "PROMOTION"} or same_team:
                if from_roster_type not in {"MAIN", "DEV"} or to_roster_type not in {"MAIN", "DEV"}:
                    errors.append(f"Item {i}: movimentação interna exige MAIN/DEV válidos.")
                elif from_roster_type == to_roster_type:
                    errors.append(f"Item {i}: movimentação interna deve trocar entre MAIN e DEV.")

        elif item_type == "pick":
            if from_team_id is None:
                errors.append(f"Item {i}: pick exige time de origem.")
                continue

            pick_ids = pick_domain_ids(data, from_team_id)
            if str(asset_id) not in pick_ids:
                errors.append(f"Item {i}: pick fora do domínio do time origem.")

            if tx_type in {"MOVE", "CALLUP", "SENDDOWN", "PROMOTION"} or same_team:
                errors.append(f"Item {i}: pick não pode ser movimentada dentro do mesmo time.")

            if tx_type in {"WAIVE", "DISPENSA", "DISMISS", "DROP"}:
                errors.append(f"Item {i}: dispensa não se aplica a pick.")

        else:
            errors.append(f"Item {i}: tipo de asset inválido.")

    return errors


def append_transaction(file_path: str, tx_row: dict, item_rows: list[dict]):
    wb = load_workbook(file_path)

    tx_df = ensure_unique_columns(load_sheet_df(wb, TX_SHEET))
    items_df = ensure_unique_columns(load_sheet_df(wb, TX_ITEMS_SHEET))

    if tx_df.empty:
        tx_df = pd.DataFrame(columns=list(tx_row.keys()))

    if items_df.empty and item_rows:
        items_df = pd.DataFrame(columns=list(item_rows[0].keys()))

    tx_df = ensure_unique_columns(tx_df)
    items_df = ensure_unique_columns(items_df)

    tx_id_col = next((c for c in tx_df.columns if str(c).strip().lower() == "transaction_id"), None)
    item_tx_id_col = next((c for c in items_df.columns if str(c).strip().lower() == "transaction_id"), None)

    if tx_id_col is None:
        tx_id_col = "transaction_id"
        if tx_id_col not in tx_df.columns:
            tx_df[tx_id_col] = pd.Series(dtype="Int64")

    if item_tx_id_col is None:
        item_tx_id_col = "transaction_id"
        if item_tx_id_col not in items_df.columns:
            items_df[item_tx_id_col] = pd.Series(dtype="Int64")

    existing_ids = pd.to_numeric(tx_df[tx_id_col], errors="coerce").dropna()
    next_tx_id = int(existing_ids.max()) + 1 if not existing_ids.empty else 1

    base_tx = dict(tx_row)
    base_tx[tx_id_col] = next_tx_id

    new_tx_rows = [base_tx]
    new_item_rows = []

    for item in item_rows or []:
        row = dict(item)
        row[item_tx_id_col] = next_tx_id
        new_item_rows.append(row)

    from_team_id = tx_row.get("from_team_id", tx_row.get("fromteamid"))
    to_team_id = tx_row.get("to_team_id", tx_row.get("toteamid"))
    tx_type = str(tx_row.get("transaction_type", tx_row.get("transactiontype", ""))).strip().upper()

    try:
        from_team_id = int(from_team_id) if from_team_id is not None and str(from_team_id).strip() != "" else None
    except Exception:
        from_team_id = None

    try:
        to_team_id = int(to_team_id) if to_team_id is not None and str(to_team_id).strip() != "" else None
    except Exception:
        to_team_id = None

    is_bilateral_trade = (
        tx_type == "TRADE"
        and from_team_id is not None
        and to_team_id is not None
        and from_team_id != to_team_id
    )

    if is_bilateral_trade:
        mirror_tx_id = next_tx_id + 1

        mirror_tx = dict(base_tx)
        if "from_team_id" in mirror_tx:
            mirror_tx["from_team_id"] = to_team_id
        if "fromteamid" in mirror_tx:
            mirror_tx["fromteamid"] = to_team_id
        if "to_team_id" in mirror_tx:
            mirror_tx["to_team_id"] = from_team_id
        if "toteamid" in mirror_tx:
            mirror_tx["toteamid"] = from_team_id
        mirror_tx[tx_id_col] = mirror_tx_id

        if "notes" in mirror_tx and mirror_tx["notes"]:
            mirror_tx["notes"] = f"{mirror_tx['notes']} [espelho]"
        elif "notes" in mirror_tx:
            mirror_tx["notes"] = "[espelho]"

        new_tx_rows.append(mirror_tx)

        for item in item_rows or []:
            mirror_item = dict(item)

            if "from_team_id" in mirror_item or "to_team_id" in mirror_item:
                old_from = mirror_item.get("from_team_id")
                old_to = mirror_item.get("to_team_id")
                mirror_item["from_team_id"] = old_to
                mirror_item["to_team_id"] = old_from

            if "fromteamid" in mirror_item or "toteamid" in mirror_item:
                old_from = mirror_item.get("fromteamid")
                old_to = mirror_item.get("toteamid")
                mirror_item["fromteamid"] = old_to
                mirror_item["toteamid"] = old_from

            if "from_roster_type" in mirror_item or "to_roster_type" in mirror_item:
                old_from_rt = mirror_item.get("from_roster_type")
                old_to_rt = mirror_item.get("to_roster_type")
                mirror_item["from_roster_type"] = old_to_rt
                mirror_item["to_roster_type"] = old_from_rt

            if "fromrostertype" in mirror_item or "torostertype" in mirror_item:
                old_from_rt = mirror_item.get("fromrostertype")
                old_to_rt = mirror_item.get("torostertype")
                mirror_item["fromrostertype"] = old_to_rt
                mirror_item["torostertype"] = old_from_rt

            mirror_item[item_tx_id_col] = mirror_tx_id
            new_item_rows.append(mirror_item)

    new_tx_df = ensure_unique_columns(pd.DataFrame(new_tx_rows))
    tx_df = pd.concat([tx_df, new_tx_df], ignore_index=True)

    if new_item_rows:
        new_items_df = ensure_unique_columns(pd.DataFrame(new_item_rows))
        items_df = pd.concat([items_df, new_items_df], ignore_index=True)

    save_sheet_df(wb, TX_SHEET, tx_df)
    if not items_df.empty:
        save_sheet_df(wb, TX_ITEMS_SHEET, items_df)

    wb.save(file_path)


def update_rosters(file_path: str, tx_row: dict, item_rows: list[dict]):
    wb = load_workbook(file_path)

    roster_df = load_sheet_df(wb, "roster")
    dev_df = load_sheet_df(wb, "development")
    picks_df = load_sheet_df(wb, "picks")

    tx_type = str(
        tx_row.get("transaction_type", tx_row.get("transactiontype", ""))
    ).strip().upper()

    from_team_raw = tx_row.get("from_team_id", tx_row.get("fromteamid"))
    to_team_raw = tx_row.get("to_team_id", tx_row.get("toteamid"))

    from_team_id = int(from_team_raw) if from_team_raw is not None and str(from_team_raw).strip() != "" else None
    to_team_id = int(to_team_raw) if to_team_raw is not None and str(to_team_raw).strip() != "" else None

    def num(series):
        return pd.to_numeric(series, errors="coerce")

    for item in item_rows:
        item_type = str(item.get("item_type", item.get("itemtype", ""))).strip().lower()
        asset_id = item.get("asset_id", item.get("assetid"))

        item_from_team_raw = item.get("from_team_id", item.get("fromteamid", from_team_id))
        item_to_team_raw = item.get("to_team_id", item.get("toteamid", to_team_id))

        item_from_team = int(item_from_team_raw) if item_from_team_raw is not None and str(item_from_team_raw).strip() != "" else None
        item_to_team = int(item_to_team_raw) if item_to_team_raw is not None and str(item_to_team_raw).strip() != "" else None

        if item_type == "player":
            pid = int(asset_id)
            from_rt = str(item.get("from_roster_type", item.get("fromrostertype", ""))).strip().upper()
            to_rt = str(item.get("to_roster_type", item.get("torostertype", ""))).strip().upper()

            if tx_type in {"WAIVE", "DISPENSA", "DISMISS", "DROP"}:
                if from_team_id is None:
                    continue

                if from_rt == "MAIN" and not roster_df.empty:
                    mask = num(roster_df["team_id"]).eq(from_team_id) & num(roster_df["player_id"]).eq(pid)
                    roster_df = roster_df.loc[~mask].copy()

                elif from_rt == "DEV" and not dev_df.empty:
                    mask = num(dev_df["team_id"]).eq(from_team_id) & num(dev_df["player_id"]).eq(pid)
                    dev_df = dev_df.loc[~mask].copy()

                continue

            if tx_type in {"ADD", "SIGN", "ASSINATURA"}:
                if item_to_team is None:
                    continue

                target_df = roster_df if to_rt == "MAIN" else dev_df
                source_df = roster_df if from_rt == "MAIN" else dev_df

                moved = False
                if item_from_team is not None and from_rt in {"MAIN", "DEV"}:
                    if not source_df.empty and "team_id" in source_df.columns and "player_id" in source_df.columns:
                        mask = num(source_df["team_id"]).eq(item_from_team) & num(source_df["player_id"]).eq(pid)
                        if mask.any():
                            moving_rows = source_df.loc[mask].copy()
                            source_df = source_df.loc[~mask].copy()
                            moving_rows.loc[:, "team_id"] = item_to_team
                            target_df = pd.concat([target_df, moving_rows], ignore_index=True)
                            moved = True

                            if from_rt == "MAIN":
                                roster_df = source_df
                            else:
                                dev_df = source_df

                            if to_rt == "MAIN":
                                roster_df = target_df
                            else:
                                dev_df = target_df

                if not moved:
                    # aqui só adiciona se você tiver uma linha-base em algum lugar;
                    # se não tiver, o SIGN pode ficar apenas em transactions por enquanto
                    pass

                continue

            if from_rt not in {"MAIN", "DEV"} or to_rt not in {"MAIN", "DEV"}:
                continue

            source_df = roster_df if from_rt == "MAIN" else dev_df
            target_df = roster_df if to_rt == "MAIN" else dev_df

            if source_df.empty or "team_id" not in source_df.columns or "player_id" not in source_df.columns:
                continue

            source_team_ids = num(source_df["team_id"])
            source_player_ids = num(source_df["player_id"])

            if item_from_team is None:
                continue

            source_mask = source_team_ids.eq(item_from_team) & source_player_ids.eq(pid)

            if not source_mask.any():
                continue

            moving_rows = source_df.loc[source_mask].copy()
            source_df = source_df.loc[~source_mask].copy()

            if item_to_team is None:
                continue

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
            if not owner_cols:
                continue

            owner_col = owner_cols[0]
            owner_ids = pd.to_numeric(picks_df[owner_col], errors="coerce")

            if tx_type in {"WAIVE", "DISPENSA", "DISMISS", "DROP"}:
                continue

            if item_from_team is None or item_to_team is None:
                continue

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
    out = out.loc[:, ~out.columns.duplicated()].copy()
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

    tx = tx.loc[:, ~tx.columns.duplicated()].copy()
    if not items.empty:
        items = items.loc[:, ~items.columns.duplicated()].copy()

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
                items.groupby("transactionid", as_index=False)["item_desc"]
                .apply(lambda s: " | ".join(s.astype(str)))
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

    tx = tx.loc[:, ~tx.columns.duplicated()].copy()

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