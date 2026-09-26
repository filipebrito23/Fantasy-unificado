import pandas as pd
import streamlit as st

from app_lib.fantasy_data_service import get_neon_connection
from sqlalchemy import text


TX_SHEET = "transactions"
TX_ITEMS_SHEET = "transactionitems"


def _to_int(value):
    try:
        return int(value) if value is not None and str(value).strip() != "" else None
    except Exception:
        return None


def _normalize_roster_type(value):
    return str(value or "").strip().upper()


def _item_value(item, *keys, default=None):
    for key in keys:
        if isinstance(item, dict) and key in item:
            val = item.get(key)
            if val is not None and str(val).strip() != "":
                return val
    return default


def roster_domain_ids(data, team_id: int, roster_type: str | None = None) -> set:
    ids = set()
    sheet_names = ["roster", "development"]
    roster_type = _normalize_roster_type(roster_type)
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

    required_columns = {"pick_id", "current_team_owner_id"}

    if not required_columns.issubset(picks.columns):
        return set()

    owner_ids = pd.to_numeric(
        picks["current_team_owner_id"],
        errors="coerce",
    )

    valid_mask = owner_ids.notna() & owner_ids.eq(int(team_id))

    return set(
        picks.loc[valid_mask, "pick_id"]
        .dropna()
        .astype(str)
        .str.strip()
        .tolist()
    )


def validate_items(data, from_team_id: int, item_rows: list[dict]) -> list[str]:
    errors = []
    for i, item in enumerate(item_rows, start=1):
        item_type = str(_item_value(item, "item_type", "itemtype", default="")).strip().lower()
        asset_id = _item_value(item, "asset_id", "assetid")
        from_roster_type = _item_value(item, "from_roster_type", "fromrostertype")
        player_ids = roster_domain_ids(data, from_team_id, from_roster_type)
        pick_ids = pick_domain_ids(data, from_team_id)
        if item_type == "player":
            asset_id_int = _to_int(asset_id)
            if asset_id_int is None or asset_id_int not in player_ids:
                errors.append(f"Item {i}: jogador fora do domínio do time origem.")
        elif item_type == "pick":
            if str(asset_id) not in pick_ids:
                errors.append(f"Item {i}: pick fora do domínio do time origem.")
        else:
            errors.append(f"Item {i}: tipo de asset inválido.")
    return errors


def validate_items_bilateral(data, item_rows: list[dict], transaction_type: str | None = None) -> list[str]:
    errors = []
    tx_type = str(transaction_type or "").strip().upper()
    for i, item in enumerate(item_rows, start=1):
        item_type = str(_item_value(item, "item_type", "itemtype", default="")).strip().lower()
        asset_id = _item_value(item, "asset_id", "assetid")
        from_team_id = _to_int(_item_value(item, "from_team_id", "fromteamid"))
        to_team_id = _to_int(_item_value(item, "to_team_id", "toteamid"))
        from_roster_type = _normalize_roster_type(_item_value(item, "from_roster_type", "fromrostertype"))
        to_roster_type = _normalize_roster_type(_item_value(item, "to_roster_type", "torostertype"))

        if tx_type == "TRADE":
            if from_team_id is None or to_team_id is None:
                errors.append(f"Item {i}: trade exige time de origem e destino.")
                continue
            if from_team_id == to_team_id:
                errors.append(f"Item {i}: trade exige times diferentes.")
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
            if from_team_id is None:
                errors.append(f"Item {i}: movimentação interna exige origem e destino.")
                continue
            if to_team_id is None:
                to_team_id = from_team_id

        same_team = from_team_id is not None and to_team_id is not None and from_team_id == to_team_id

        if item_type == "player":
            asset_id_int = _to_int(asset_id)
            if asset_id_int is None:
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


def save_and_apply_transaction_neon(
    tx_row: dict,
    item_rows: list[dict],
    source_transaction_id: int,
) -> int:
    """
    Cria e aplica uma transaction no Neon, em uma única transação SQL.

    Retorna o ID da transaction recém-criada (fantasy_transaction_id).
    """
    tx_type = str(
        tx_row.get("transaction_type", tx_row.get("transactiontype", ""))
    ).strip().upper()

    tx_date = tx_row.get("transaction_date", tx_row.get("transactiondate"))
    initiated_by = tx_row.get("initiated_by", tx_row.get("initiatedby"))
    notes = tx_row.get("notes")
    season = tx_row.get("season")

    with get_neon_connection() as conn:
        # ---------------------------------------------------------
        # Cabeçalho da transaction
        # ---------------------------------------------------------
        result = conn.execute(
            text(
                """
                INSERT INTO fantasy_transactions (
                    source_transaction_id,
                    transaction_type,
                    transaction_date,
                    from_team_id,
                    to_team_id,
                    initiated_by,
                    status,
                    notes,
                    season
                )
                VALUES (
                    :source_transaction_id,
                    :transaction_type,
                    :transaction_date,
                    :from_team_id,
                    :to_team_id,
                    :initiated_by,
                    :status,
                    :notes,
                    :season
                )
                RETURNING fantasy_transaction_id;
                """
            ),
            {
                "source_transaction_id": source_transaction_id,
                "transaction_type": tx_type,
                "transaction_date": tx_date,
                "from_team_id": tx_row.get("from_team_id", tx_row.get("fromteamid")),
                "to_team_id": tx_row.get("to_team_id", tx_row.get("toteamid")),
                "initiated_by": initiated_by,
                "status": "completed",
                "notes": notes,
                "season": season,
            },
        )

        (fantasy_transaction_id,) = result.fetchone()

        # ---------------------------------------------------------
        # Itens da transaction
        # ---------------------------------------------------------
        for item in item_rows:
            item_type = str(
                _item_value(item, "item_type", "itemtype", default="")
            ).strip().lower()

            asset_id = _item_value(item, "asset_id", "assetid")

            from_team_id = _to_int(
                _item_value(
                    item,
                    "from_team_id",
                    "fromteamid",
                    default=tx_row.get("from_team_id", tx_row.get("fromteamid")),
                )
            )

            to_team_id = _to_int(
                _item_value(
                    item,
                    "to_team_id",
                    "toteamid",
                    default=tx_row.get("to_team_id", tx_row.get("toteamid")),
                )
            )

            from_roster_type = _normalize_roster_type(
                _item_value(
                    item,
                    "from_roster_type",
                    "fromrostertype",
                )
            )

            to_roster_type = _normalize_roster_type(
                _item_value(
                    item,
                    "to_roster_type",
                    "torostertype",
                )
            )

            # Converte asset_id para as colunas corretas
            player_source_id = None
            pick_source_id = None

            if item_type == "player":
                player_source_id = _to_int(asset_id)
            elif item_type == "pick":
                pick_source_id = str(asset_id).strip() if asset_id is not None else None

            conn.execute(
                text(
                    """
                    INSERT INTO fantasy_transaction_items (
                        fantasy_transaction_id,
                        item_type,
                        player_source_id,
                        pick_source_id,
                        from_team_id,
                        to_team_id,
                        from_roster_type,
                        to_roster_type,
                        source_sheet
                    )
                    VALUES (
                        :fantasy_transaction_id,
                        :item_type,
                        :player_source_id,
                        :pick_source_id,
                        :from_team_id,
                        :to_team_id,
                        :from_roster_type,
                        :to_roster_type,
                        :source_sheet
                    );
                    """
                ),
                {
                    "fantasy_transaction_id": fantasy_transaction_id,
                    "item_type": item_type,
                    "player_source_id": player_source_id,
                    "pick_source_id": pick_source_id,
                    "from_team_id": from_team_id,
                    "to_team_id": to_team_id,
                    "from_roster_type": from_roster_type or None,
                    "to_roster_type": to_roster_type or None,
                    "source_sheet": "transactions",
                },
            )
        # ---------------------------------------------------------
        # Aplicar efeitos no roster / development / picks
        # ---------------------------------------------------------
        for item in item_rows:
            item_type = str(
                _item_value(item, "item_type", "itemtype", default="")
            ).strip().lower()

            asset_id = _item_value(item, "asset_id", "assetid")

            from_team_id = _to_int(
                _item_value(
                    item,
                    "from_team_id",
                    "fromteamid",
                    default=tx_row.get("from_team_id", tx_row.get("fromteamid")),
                )
            )

            to_team_id = _to_int(
                _item_value(
                    item,
                    "to_team_id",
                    "toteamid",
                    default=tx_row.get("to_team_id", tx_row.get("toteamid")),
                )
            )

            from_roster_type = _normalize_roster_type(
                _item_value(
                    item,
                    "from_roster_type",
                    "fromrostertype",
                )
            )

            to_roster_type = _normalize_roster_type(
                _item_value(
                    item,
                    "to_roster_type",
                    "torostertype",
                )
            )

            # -----------------------------------------------------
            # PICKS
            # -----------------------------------------------------
            if item_type == "pick":
                if tx_type in {"WAIVE", "DISPENSA", "DISMISS", "DROP"}:
                    continue

                if tx_type in {
                    "MOVE",
                    "CALLUP",
                    "SENDDOWN",
                    "PROMOTION",
                }:
                    continue

                if from_team_id is None or to_team_id is None:
                    continue

                conn.execute(
                    text(
                        """
                        UPDATE fantasy_picks
                        SET current_team_owner_id = :to_team_id
                        WHERE source_pick_id = :pick_id
                          AND current_team_owner_id = :from_team_id;
                        """
                    ),
                    {
                        "pick_id": str(asset_id).strip().upper(),
                        "from_team_id": from_team_id,
                        "to_team_id": to_team_id,
                    },
                )

                continue

            # -----------------------------------------------------
            # JOGADORES
            # -----------------------------------------------------
            if item_type != "player":
                continue

            pid = _to_int(asset_id)

            if pid is None:
                continue

            # -------------------------------------------------
            # Busca os salários e opções no roster de origem
            # -------------------------------------------------
            if from_roster_type == "DEV":
                source_table = "fantasy_development"
            else:
                source_table = "fantasy_roster"

            player_result = conn.execute(
                text(
                    f"""
                    SELECT
                        salarie_26_27,
                        option_26_27,
                        salarie_27_28,
                        option_27_28,
                        salarie_28_29,
                        option_28_29,
                        salarie_29_30,
                        option_29_30
                    FROM {source_table}
                    WHERE source_player_id = :player_id
                      AND team_id = :team_id;
                    """
                ),
                {
                    "player_id": pid,
                    "team_id": from_team_id,
                },
            )

            player_row = player_result.fetchone()

            if player_row is None:
                # Jogador não encontrado no roster de origem; pula para evitar erro.
                continue

            salarie_26_27 = player_row[0]
            option_26_27 = player_row[1]
            salarie_27_28 = player_row[2]
            option_27_28 = player_row[3]
            salarie_28_29 = player_row[4]
            option_28_29 = player_row[5]
            salarie_29_30 = player_row[6]
            option_29_30 = player_row[7]

            # TRADE
            if tx_type == "TRADE":
                if from_team_id is None or to_team_id is None:
                    continue

                if to_roster_type not in {"MAIN", "DEV"}:
                    to_roster_type = "MAIN"

                # Remove da origem
                if from_roster_type == "DEV":
                    conn.execute(
                        text(
                            """
                            DELETE FROM fantasy_development
                            WHERE source_player_id = :player_id
                              AND team_id = :team_id;
                            """
                        ),
                        {
                            "player_id": pid,
                            "team_id": from_team_id,
                        },
                    )
                else:
                    conn.execute(
                        text(
                            """
                            DELETE FROM fantasy_roster
                            WHERE source_player_id = :player_id
                              AND team_id = :team_id;
                            """
                        ),
                        {
                            "player_id": pid,
                            "team_id": from_team_id,
                        },
                    )

                # Insere no destino
                if to_roster_type == "DEV":
                    conn.execute(
                        text(
                            """
                            INSERT INTO fantasy_development (
                                team_id,
                                source_player_id,
                                salarie_26_27,
                                option_26_27,
                                salarie_27_28,
                                option_27_28,
                                salarie_28_29,
                                option_28_29,
                                salarie_29_30,
                                option_29_30,
                                source_sheet
                            )
                            VALUES (
                                :team_id,
                                :player_id,
                                :salarie_26_27,
                                :option_26_27,
                                :salarie_27_28,
                                :option_27_28,
                                :salarie_28_29,
                                :option_28_29,
                                :salarie_29_30,
                                :option_29_30,
                                :source_sheet
                            );
                            """
                        ),
                        {
                            "team_id": to_team_id,
                            "player_id": pid,
                            "salarie_26_27": salarie_26_27,
                            "option_26_27": option_26_27,
                            "salarie_27_28": salarie_27_28,
                            "option_27_28": option_27_28,
                            "salarie_28_29": salarie_28_29,
                            "option_28_29": option_28_29,
                            "salarie_29_30": salarie_29_30,
                            "option_29_30": option_29_30,
                            "source_sheet": "development",
                        },
                    )
                else:
                    conn.execute(
                        text(
                            """
                            INSERT INTO fantasy_roster (
                                team_id,
                                source_player_id,
                                salarie_26_27,
                                option_26_27,
                                salarie_27_28,
                                option_27_28,
                                salarie_28_29,
                                option_28_29,
                                salarie_29_30,
                                option_29_30,
                                source_sheet
                            )
                            VALUES (
                                :team_id,
                                :player_id,
                                :salarie_26_27,
                                :option_26_27,
                                :salarie_27_28,
                                :option_27_28,
                                :salarie_28_29,
                                :option_28_29,
                                :salarie_29_30,
                                :option_29_30,
                                :source_sheet
                            );
                            """
                        ),
                        {
                            "team_id": to_team_id,
                            "player_id": pid,
                            "salarie_26_27": salarie_26_27,
                            "option_26_27": option_26_27,
                            "salarie_27_28": salarie_27_28,
                            "option_27_28": option_27_28,
                            "salarie_28_29": salarie_28_29,
                            "option_28_29": option_28_29,
                            "salarie_29_30": salarie_29_30,
                            "option_29_30": option_29_30,
                            "source_sheet": "roster",
                        },
                    )

                continue

            # WAIVE
            if tx_type in {"WAIVE", "DISPENSA", "DISMISS", "DROP"}:
                if from_team_id is None:
                    continue

                if from_roster_type == "DEV":
                    conn.execute(
                        text(
                            """
                            DELETE FROM fantasy_development
                            WHERE source_player_id = :player_id
                              AND team_id = :team_id;
                            """
                        ),
                        {
                            "player_id": pid,
                            "team_id": from_team_id,
                        },
                    )
                else:
                    conn.execute(
                        text(
                            """
                            DELETE FROM fantasy_roster
                            WHERE source_player_id = :player_id
                              AND team_id = :team_id;
                            """
                        ),
                        {
                            "player_id": pid,
                            "team_id": from_team_id,
                        },
                    )

                continue

            # ADD / SIGN
            if tx_type in {"ADD", "SIGN", "ASSINATURA"}:
                if from_team_id is None or to_team_id is None:
                    continue

                # Remove da origem
                if from_roster_type == "DEV":
                    conn.execute(
                        text(
                            """
                            DELETE FROM fantasy_development
                            WHERE source_player_id = :player_id
                              AND team_id = :team_id;
                            """
                        ),
                        {
                            "player_id": pid,
                            "team_id": from_team_id,
                        },
                    )
                else:
                    conn.execute(
                        text(
                            """
                            DELETE FROM fantasy_roster
                            WHERE source_player_id = :player_id
                              AND team_id = :team_id;
                            """
                        ),
                        {
                            "player_id": pid,
                            "team_id": from_team_id,
                        },
                    )

                # Insere no destino
                if to_roster_type == "DEV":
                    conn.execute(
                        text(
                            """
                            INSERT INTO fantasy_development (
                                team_id,
                                source_player_id,
                                salarie_26_27,
                                option_26_27,
                                salarie_27_28,
                                option_27_28,
                                salarie_28_29,
                                option_28_29,
                                salarie_29_30,
                                option_29_30,
                                source_sheet
                            )
                            VALUES (
                                :team_id,
                                :player_id,
                                :salarie_26_27,
                                :option_26_27,
                                :salarie_27_28,
                                :option_27_28,
                                :salarie_28_29,
                                :option_28_29,
                                :salarie_29_30,
                                :option_29_30,
                                :source_sheet
                            );
                            """
                        ),
                        {
                            "team_id": to_team_id,
                            "player_id": pid,
                            "salarie_26_27": salarie_26_27,
                            "option_26_27": option_26_27,
                            "salarie_27_28": salarie_27_28,
                            "option_27_28": option_27_28,
                            "salarie_28_29": salarie_28_29,
                            "option_28_29": option_28_29,
                            "salarie_29_30": salarie_29_30,
                            "option_29_30": option_29_30,
                            "source_sheet": "development",
                        },
                    )
                else:
                    conn.execute(
                        text(
                            """
                            INSERT INTO fantasy_roster (
                                team_id,
                                source_player_id,
                                salarie_26_27,
                                option_26_27,
                                salarie_27_28,
                                option_27_28,
                                salarie_28_29,
                                option_28_29,
                                salarie_29_30,
                                option_29_30,
                                source_sheet
                            )
                            VALUES (
                                :team_id,
                                :player_id,
                                :salarie_26_27,
                                :option_26_27,
                                :salarie_27_28,
                                :option_27_28,
                                :salarie_28_29,
                                :option_28_29,
                                :salarie_29_30,
                                :option_29_30,
                                :source_sheet
                            );
                            """
                        ),
                        {
                            "team_id": to_team_id,
                            "player_id": pid,
                            "salarie_26_27": salarie_26_27,
                            "option_26_27": option_26_27,
                            "salarie_27_28": salarie_27_28,
                            "option_27_28": option_27_28,
                            "salarie_28_29": salarie_28_29,
                            "option_28_29": option_28_29,
                            "salarie_29_30": salarie_29_30,
                            "option_29_30": option_29_30,
                            "source_sheet": "roster",
                        },
                    )

                continue

            # MOVE / CALLUP / SENDDOWN / PROMOTION
            if tx_type in {
                "MOVE",
                "CALLUP",
                "SENDDOWN",
                "PROMOTION",
            }:
                if (
                    from_roster_type not in {"MAIN", "DEV"}
                    or to_roster_type not in {"MAIN", "DEV"}
                    or from_team_id is None
                ):
                    continue

                # Remove da origem
                if from_roster_type == "DEV":
                    conn.execute(
                        text(
                            """
                            DELETE FROM fantasy_development
                            WHERE source_player_id = :player_id
                              AND team_id = :team_id;
                            """
                        ),
                        {
                            "player_id": pid,
                            "team_id": from_team_id,
                        },
                    )
                else:
                    conn.execute(
                        text(
                            """
                            DELETE FROM fantasy_roster
                            WHERE source_player_id = :player_id
                              AND team_id = :team_id;
                            """
                        ),
                        {
                            "player_id": pid,
                            "team_id": from_team_id,
                        },
                    )

                # Insere no destino (mesmo time, outro roster)
                if to_roster_type == "DEV":
                    conn.execute(
                        text(
                            """
                            INSERT INTO fantasy_development (
                                team_id,
                                source_player_id,
                                salarie_26_27,
                                option_26_27,
                                salarie_27_28,
                                option_27_28,
                                salarie_28_29,
                                option_28_29,
                                salarie_29_30,
                                option_29_30,
                                source_sheet
                            )
                            VALUES (
                                :team_id,
                                :player_id,
                                :salarie_26_27,
                                :option_26_27,
                                :salarie_27_28,
                                :option_27_28,
                                :salarie_28_29,
                                :option_28_29,
                                :salarie_29_30,
                                :option_29_30,
                                :source_sheet
                            );
                            """
                        ),
                        {
                            "team_id": from_team_id,
                            "player_id": pid,
                            "salarie_26_27": salarie_26_27,
                            "option_26_27": option_26_27,
                            "salarie_27_28": salarie_27_28,
                            "option_27_28": option_27_28,
                            "salarie_28_29": salarie_28_29,
                            "option_28_29": option_28_29,
                            "salarie_29_30": salarie_29_30,
                            "option_29_30": option_29_30,
                            "source_sheet": "development",
                        },
                    )
                else:
                    conn.execute(
                        text(
                            """
                            INSERT INTO fantasy_roster (
                                team_id,
                                source_player_id,
                                salarie_26_27,
                                option_26_27,
                                salarie_27_28,
                                option_27_28,
                                salarie_28_29,
                                option_28_29,
                                salarie_29_30,
                                option_29_30,
                                source_sheet
                            )
                            VALUES (
                                :team_id,
                                :player_id,
                                :salarie_26_27,
                                :option_26_27,
                                :salarie_27_28,
                                :option_27_28,
                                :salarie_28_29,
                                :option_28_29,
                                :salarie_29_30,
                                :option_29_30,
                                :source_sheet
                            );
                            """
                        ),
                        {
                            "team_id": from_team_id,
                            "player_id": pid,
                            "salarie_26_27": salarie_26_27,
                            "option_26_27": option_26_27,
                            "salarie_27_28": salarie_27_28,
                            "option_27_28": option_27_28,
                            "salarie_28_29": salarie_28_29,
                            "option_28_29": option_28_29,
                            "salarie_29_30": salarie_29_30,
                            "option_29_30": option_29_30,
                            "source_sheet": "roster",
                        },
                    )

                continue

        # O commit é automático ao sair do with, se não houver erro.
        return fantasy_transaction_id


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

    def normalize_transaction_id(value) -> str | None:
        if value is None or pd.isna(value):
            return None

        try:
            return str(int(float(value)))
        except (TypeError, ValueError):
            text_value = str(value).strip()
            return text_value if text_value else None

    def normalize_team_id(value) -> int | None:
        if value is None or pd.isna(value):
            return None

        try:
            return int(float(value))
        except (TypeError, ValueError):
            return None

    tx = compact_columns(tx_df)
    items = (
        compact_columns(items_df)
        if items_df is not None and not items_df.empty
        else pd.DataFrame()
    )

    tx = tx.loc[:, ~tx.columns.duplicated()].copy()

    required_tx_columns = {
        "transactionid",
        "fromteamid",
        "toteamid",
    }

    if not required_tx_columns.issubset(tx.columns):
        return pd.DataFrame()

    selected_team_id = int(selected_team_id)

    tx["__transaction_key__"] = tx["transactionid"].apply(
        normalize_transaction_id
    )
    tx["__from_team_id__"] = tx["fromteamid"].apply(
        normalize_team_id
    )
    tx["__to_team_id__"] = tx["toteamid"].apply(
        normalize_team_id
    )

    tx = tx.loc[
        tx["__from_team_id__"].eq(selected_team_id)
        | tx["__to_team_id__"].eq(selected_team_id)
    ].copy()

    if tx.empty:
        return pd.DataFrame()

    tx["from_team"] = tx["__from_team_id__"].map(team_lookup).fillna(
        tx["fromteamid"]
    )
    tx["to_team"] = tx["__to_team_id__"].map(team_lookup).fillna(
        tx["toteamid"]
    )

    items_by_transaction: dict[str, list[dict]] = {}

    if not items.empty and "transactionid" in items.columns:
        items = items.copy()

        items["__transaction_key__"] = items["transactionid"].apply(
            normalize_transaction_id
        )
        items["__from_team_id__"] = items["fromteamid"].apply(
            normalize_team_id
        )
        items["__to_team_id__"] = items["toteamid"].apply(
            normalize_team_id
        )

        valid_transaction_keys = set(
            tx["__transaction_key__"].dropna().tolist()
        )

        items = items.loc[
            items["__transaction_key__"].isin(valid_transaction_keys)
        ].copy()

        for _, item in items.iterrows():
            transaction_key = item.get("__transaction_key__")

            if not transaction_key:
                continue

            item_type = str(
                item.get("itemtype", "")
            ).strip().lower()

            asset_id = item.get("assetid")

            from_team_id = item.get("__from_team_id__")
            to_team_id = item.get("__to_team_id__")

            from_roster_type = str(
                item.get("fromrostertype", "") or ""
            ).strip().upper()

            to_roster_type = str(
                item.get("torostertype", "") or ""
            ).strip().upper()

            if item_type == "player":
                player_id = normalize_team_id(asset_id)

                if player_id is None:
                    asset_label = str(asset_id)
                else:
                    asset_label = player_lookup.get(
                        player_id,
                        f"Jogador #{player_id}",
                    )

            elif item_type == "pick":
                asset_label = str(asset_id).strip()

            else:
                asset_label = str(asset_id).strip()

            roster_label = ""

            if from_roster_type or to_roster_type:
                roster_label = (
                    f" [{from_roster_type or '-'}"
                    f" → {to_roster_type or '-'}]"
                )

            items_by_transaction.setdefault(
                str(transaction_key),
                [],
            ).append(
                {
                    "from_team_id": from_team_id,
                    "to_team_id": to_team_id,
                    "label": f"{asset_label}{roster_label}",
                }
            )

    sent_values: list[str] = []
    received_values: list[str] = []
    all_items_values: list[str] = []

    for _, tx_row in tx.iterrows():
        transaction_key = tx_row.get("__transaction_key__")
        transaction_items = items_by_transaction.get(
            str(transaction_key),
            [],
        )

        sent_items = [
            item["label"]
            for item in transaction_items
            if item.get("from_team_id") == selected_team_id
        ]

        received_items = [
            item["label"]
            for item in transaction_items
            if item.get("to_team_id") == selected_team_id
        ]

        all_items = [
            item["label"]
            for item in transaction_items
        ]

        sent_values.append(
            " | ".join(sent_items) if sent_items else "-"
        )
        received_values.append(
            " | ".join(received_items) if received_items else "-"
        )
        all_items_values.append(
            " | ".join(all_items) if all_items else "-"
        )

    tx["enviado"] = sent_values
    tx["recebido"] = received_values
    tx["itens"] = all_items_values

    tx = tx.rename(
        columns={
            "transactionid": "transaction_id",
            "transactiontype": "transaction_type",
            "transactiondate": "transaction_date",
            "initiatedby": "initiated_by",
        }
    )

    tx = tx.loc[:, ~tx.columns.duplicated()].copy()

    preferred_columns = [
        "transaction_date",
        "season",
        "from_team",
        "to_team",
        "enviado",
        "recebido",
        "notes",
    ]

    existing_columns = [
        column
        for column in preferred_columns
        if column in tx.columns
    ]

    sort_columns = [
        column
        for column in ["transaction_date", "transaction_id"]
        if column in tx.columns
    ]

    if sort_columns:
        tx = tx.sort_values(
            by=sort_columns,
            ascending=False,
            kind="stable",
        )

    return tx[existing_columns].reset_index(drop=True)