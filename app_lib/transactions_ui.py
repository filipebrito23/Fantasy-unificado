from __future__ import annotations

from typing import Any

import pandas as pd
import streamlit as st

from app_lib.transactions_service import (
    TX_ITEMS_SHEET,
    TX_SHEET,
    append_transaction,
    validate_items_bilateral,
    pick_domain_ids,
    update_rosters,
)
from app_lib.transactions_form_helpers import (
    build_prepared_items,
    build_tx_row,
    collect_valid_item_rows,
    get_player_ids_from_team,
    get_player_labels,
    get_team_id_map,
    get_transaction_default_team_options,
    make_next_transaction_id,
    normalize_transaction_display_df,
    validate_transaction_form,
)
from app_lib.transforms import SEASON_LABELS, SEASONS


def _get_team_player_source_df(
    data: dict[str, pd.DataFrame],
    team_id: int | None,
    roster_type: str | None,
) -> pd.DataFrame:
    if team_id is None or roster_type is None:
        return pd.DataFrame()
    if roster_type == "MAIN":
        return data["roster"].loc[data["roster"]["team_id"] == team_id].copy()
    return data["development"].loc[data["development"]["team_id"] == team_id].copy()


def _render_asset_row(
    *,
    prefix: str,
    i: int,
    side_label: str,
    team_name: str,
    team_id: int | None,
    data: dict[str, pd.DataFrame],
    player_lookup: dict[int, str],
    pick_options: list[Any],
    allow_roster_move: bool,
) -> dict[str, Any]:
    st.markdown(f"**Item {i + 1} - {team_name}**")
    c1, c2, c3, c4 = st.columns(4)

    with c1:
        item_type = st.selectbox(
            "Tipo",
            ["player", "pick"],
            key=f"{prefix}_item_type_{i}",
        )

    from_roster_type = None
    to_roster_type = None
    selected_asset: Any = None

    if item_type == "player":
        with c2:
            from_roster_type = st.selectbox(
                "Origem do jogador",
                ["MAIN", "DEV"],
                key=f"{prefix}_roster_type_{i}",
            )

        source_df = _get_team_player_source_df(data, team_id, from_roster_type)
        player_ids = get_player_ids_from_team(source_df)
        player_labels = get_player_labels(player_lookup, player_ids)

        with c3:
            selected_asset = (
                st.selectbox(
                    "Jogador",
                    options=player_ids,
                    format_func=lambda x: player_labels.get(x, str(x)),
                    key=f"{prefix}_asset_player_{i}",
                )
                if player_ids
                else st.selectbox(
                    "Jogador",
                    options=[None],
                    format_func=lambda x: "Sem jogadores disponíveis",
                    key=f"{prefix}_asset_player_empty_{i}",
                )
            )

        with c4:
            if allow_roster_move:
                roster_dest_options = [rt for rt in ["MAIN", "DEV"] if rt != from_roster_type]
                to_roster_type = st.selectbox(
                    "Destino do jogador",
                    roster_dest_options,
                    key=f"{prefix}_to_roster_type_{i}",
                )
            else:
                st.selectbox(
                    "Destino do jogador",
                    ["-"],
                    key=f"{prefix}_to_roster_type_placeholder_{i}",
                    disabled=True,
                )
    else:
        with c2:
            st.selectbox(
                "Origem do jogador",
                ["-"],
                key=f"{prefix}_roster_type_placeholder_{i}",
                disabled=True,
            )

        with c3:
            selected_asset = (
                st.selectbox(
                    "Pick",
                    options=pick_options,
                    key=f"{prefix}_asset_pick_{i}",
                )
                if pick_options
                else st.selectbox(
                    "Pick",
                    options=[None],
                    format_func=lambda x: "Sem picks disponíveis",
                    key=f"{prefix}_asset_pick_empty_{i}",
                )
            )

        with c4:
            st.selectbox(
                "Destino do jogador",
                ["-"],
                key=f"{prefix}_to_roster_type_placeholder_pick_{i}",
                disabled=True,
            )

    return {
        "item_id": i + 1 if side_label == "Time A" else 100 + i + 1,
        "item_type": item_type,
        "asset_id": selected_asset,
        "from_team_id": team_id,
        "to_team_id": None,
        "from_roster_type": from_roster_type,
        "to_roster_type": to_roster_type,
    }


def _render_side_items(
    *,
    side_label: str,
    prefix: str,
    team_name: str,
    team_id: int | None,
    data: dict[str, pd.DataFrame],
    player_lookup: dict[int, str],
    pick_options: list[Any],
    allow_roster_move: bool,
    default_count: int,
) -> list[dict[str, Any]]:
    st.markdown(f"### Assets do {side_label}")
    side_count = st.number_input(
        f"Quantidade de assets do {side_label}",
        min_value=0,
        max_value=10,
        value=default_count,
        step=1,
        key=f"{prefix}_side_count_v4",
    )
    side_items = []
    for i in range(int(side_count)):
        side_items.append(
            _render_asset_row(
                prefix=prefix,
                i=i,
                side_label=side_label,
                team_name=team_name,
                team_id=team_id,
                data=data,
                player_lookup=player_lookup,
                pick_options=pick_options,
                allow_roster_move=allow_roster_move,
            )
        )
    return side_items


def render_transactions_tab(
    *,
    data: dict[str, pd.DataFrame],
    teams: pd.DataFrame,
    selected_team_id: int,
    team_transactions_df: pd.DataFrame,
    team_lookup: dict[int, str],
    player_lookup: dict[int, str],
    user: Any,
    is_admin: bool,
    DEFAULT_FILE: Any,
) -> None:
    if is_admin:
        with st.expander("Registrar nova transaction", expanded=False):
            tx_base_df = data.get(TX_SHEET, pd.DataFrame())
            transaction_items_df = data.get(TX_ITEMS_SHEET, pd.DataFrame())

            team_options = get_transaction_default_team_options(teams)
            team_name_to_id = get_team_id_map(teams)

            tx_type = st.selectbox(
                "Tipo de transaction",
                ["TRADE", "WAIVE", "ADD", "MOVE", "OTHER"],
                key="tx_type_v4",
            )
            tx_season = st.selectbox(
                "Season",
                SEASONS,
                format_func=lambda x: SEASON_LABELS[x],
                key="tx_season_v4",
            )

            show_to_team = tx_type == "TRADE"
            col_a, col_b = st.columns(2)
            with col_a:
                from_team_name = st.selectbox("Time A", team_options, key="tx_from_team_v4")
            with col_b:
                if show_to_team:
                    to_team_name = st.selectbox("Time B", team_options, key="tx_to_team_v4")
                else:
                    to_team_name = "-- Nenhum --"
                    st.selectbox(
                        "Time B",
                        ["-- Nenhum --"],
                        key="tx_to_team_v4_locked",
                        disabled=True,
                    )

            from_team_id = int(team_name_to_id[from_team_name]) if from_team_name in team_name_to_id else None
            to_team_id = int(team_name_to_id[to_team_name]) if to_team_name in team_name_to_id else None

            if tx_type == "WAIVE":
                to_team_id = None
            if tx_type == "ADD":
                from_team_id = None
            if tx_type == "MOVE":
                to_team_id = from_team_id

            same_team = from_team_id is not None and to_team_id is not None and from_team_id == to_team_id
            if tx_type == "MOVE":
                st.info("Movimentação interna do mesmo time: use isso para promover/demover entre MAIN e DEV.")
            elif same_team and tx_type == "TRADE":
                st.warning("TRADE precisa envolver times diferentes.")

            col_c, col_d, col_e = st.columns(3)
            with col_c:
                tx_date = st.date_input("Data", key="tx_date_v4")
            with col_d:
                initiated_by_value = (
                    str(user.get("name") or user.get("username") or user.get("email") or user)
                    if isinstance(user, dict)
                    else str(user)
                )
                initiated_by = st.text_input("Iniciado por", value=initiated_by_value, key="tx_initiated_by_v4")
            with col_e:
                tx_status = st.selectbox("Status", ["PENDING", "APPROVED", "DONE"], index=2, key="tx_status_v4")

            tx_notes = st.text_area("Observações", key="tx_notes_v4")

            from_default = 1 if tx_type in {"TRADE", "WAIVE", "MOVE", "OTHER"} else 0
            from_pick_options = pick_domain_ids(data, from_team_id) if from_team_id is not None else []
            from_side_items = _render_side_items(
                side_label="Time A",
                prefix="from",
                team_name=from_team_name,
                team_id=from_team_id,
                data=data,
                player_lookup=player_lookup,
                pick_options=sorted(from_pick_options),
                allow_roster_move=(tx_type == "MOVE"),
                default_count=from_default,
            )

            to_side_items = []
            if show_to_team:
                to_pick_options = pick_domain_ids(data, to_team_id) if to_team_id is not None else []
                to_side_items = _render_side_items(
                    side_label="Time B",
                    prefix="to",
                    team_name=to_team_name,
                    team_id=to_team_id,
                    data=data,
                    player_lookup=player_lookup,
                    pick_options=sorted(to_pick_options),
                    allow_roster_move=False,
                    default_count=1,
                )

            all_item_rows = from_side_items + to_side_items
            save_tx = st.button("Salvar transaction", type="primary", key="save_tx_v4")

            if save_tx:
                valid_item_rows, form_errors = collect_valid_item_rows(all_item_rows)
                form_errors.extend(validate_transaction_form(tx_type, from_team_id, to_team_id, valid_item_rows))
                form_errors.extend(validate_items_bilateral(data, valid_item_rows, tx_type))

                if form_errors:
                    for err in form_errors:
                        st.error(err)
                else:
                    next_tx_id, _ = make_next_transaction_id(tx_base_df, start=1)
                    tx_row = build_tx_row(
                        tx_base_df=tx_base_df,
                        next_tx_id=next_tx_id,
                        tx_date=tx_date,
                        tx_type=tx_type,
                        tx_season=tx_season,
                        from_team_id=from_team_id,
                        to_team_id=to_team_id,
                        initiated_by=initiated_by,
                        tx_status=tx_status,
                        tx_notes=tx_notes,
                    )
                    prepared_items = build_prepared_items(transaction_items_df, next_tx_id, valid_item_rows)
                    append_transaction(str(DEFAULT_FILE), tx_row, prepared_items)
                    update_rosters(str(DEFAULT_FILE), tx_row, prepared_items)
                    st.cache_data.clear()
                    st.success("Transaction salva e aplicada com sucesso.")
                    st.rerun()

    st.subheader("Histórico de transactions")
    if team_transactions_df.empty:
        st.info("Esse time ainda não possui transactions registradas.")
        return

    filter_col1, filter_col2, filter_col3 = st.columns(3)
    type_options = ["Todas"]
    if "transaction_type" in team_transactions_df.columns:
        type_options += sorted(team_transactions_df["transaction_type"].dropna().astype(str).unique().tolist())
    status_options = ["Todos"]
    if "status" in team_transactions_df.columns:
        status_options += sorted(team_transactions_df["status"].dropna().astype(str).unique().tolist())
    season_options = ["Todas"]
    if "season" in team_transactions_df.columns:
        season_options += sorted(team_transactions_df["season"].dropna().astype(str).unique().tolist())

    with filter_col1:
        selected_tx_type = st.selectbox("Tipo", type_options, key="tx_history_type_v4")
    with filter_col2:
        selected_tx_status = st.selectbox("Status", status_options, key="tx_history_status_v4")
    with filter_col3:
        selected_tx_season = st.selectbox("Season", season_options, key="tx_history_season_v4")

    filtered_tx = team_transactions_df.copy()
    if selected_tx_type != "Todas" and "transaction_type" in filtered_tx.columns:
        filtered_tx = filtered_tx.loc[filtered_tx["transaction_type"].astype(str) == selected_tx_type]
    if selected_tx_status != "Todos" and "status" in filtered_tx.columns:
        filtered_tx = filtered_tx.loc[filtered_tx["status"].astype(str) == selected_tx_status]
    if selected_tx_season != "Todas" and "season" in filtered_tx.columns:
        filtered_tx = filtered_tx.loc[filtered_tx["season"].astype(str) == selected_tx_season]

    metric_cols = st.columns(3)
    metric_cols[0].metric("Transactions", len(filtered_tx))
    metric_cols[1].metric("Tipos distintos", filtered_tx["transaction_type"].nunique() if "transaction_type" in filtered_tx.columns else 0)
    metric_cols[2].metric("Seasons", filtered_tx["season"].nunique() if "season" in filtered_tx.columns else 0)

    display_tx = normalize_transaction_display_df(filtered_tx)
    st.dataframe(display_tx, use_container_width=True, hide_index=True)