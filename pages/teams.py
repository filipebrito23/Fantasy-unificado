from pathlib import Path
from app_lib.permissions import require_admin_page, admin_only_action, is_admin_user
import pandas as pd
import streamlit as st

from app_lib.data_loader import load_workbook_data, SEASONS
from app_lib.transforms import (
    SEASON_LABELS,
    build_picks_view,
    format_picks_for_display,
    get_team_options,
    get_visible_seasons,
    build_roster_view,
    format_roster_for_display,
    calculate_main_totals,
    calculate_dev_totals,
    summarize_positions,
    summarize_picks_by_year,
)
from app_lib.excel_utils import get_next_id
from app_lib.transactions_service import (
    TX_SHEET,
    TX_ITEMS_SHEET,
    pick_domain_ids,
    update_rosters,
    append_transaction,
    build_transactions_history,
    validate_items_bilateral,
)
from app_lib.teams_ui_helpers import (
    currency,
    build_red_flags,
    get_roster_column_order,
    get_roster_column_config,
    get_picks_column_order,
    get_picks_column_config,
    inject_summary_card_css,
    render_summary_card,
)

DEFAULT_FILE = Path("roster.xlsx")


def require_login_v5():
    if "user_v5" not in st.session_state or not st.session_state.user_v5:
        st.warning("Faça login para acessar esta página.")
        st.stop()
    return st.session_state.user_v5


@st.cache_data
def cached_load(file_path: str):
    return load_workbook_data(file_path)


user = require_login_v5()
is_admin = is_admin_user(user)

st.title("Elencos Fantasy NBA")
st.caption("Elencos 2026-27")

if not DEFAULT_FILE.exists():
    st.error("Arquivo roster.xlsx não encontrado na pasta do projeto.")
    st.stop()

data = cached_load(str(DEFAULT_FILE))
teams = get_team_options(data["teams"])

if teams.empty:
    st.error("Nenhum time encontrado nos dados carregados.")
    st.stop()

if "teams_selected_team_name_v1" not in st.session_state:
    st.session_state["teams_selected_team_name_v1"] = teams["team_name"].tolist()[0]

if "teams_selected_start_season_v1" not in st.session_state:
    st.session_state["teams_selected_start_season_v1"] = SEASONS[0]

team_map = (
    data["teams"][["team_id", "team_name"]].drop_duplicates()
    if not data["teams"].empty
    else pd.DataFrame(columns=["team_id", "team_name"])
)
team_lookup = dict(zip(team_map["team_id"], team_map["team_name"])) if not team_map.empty else {}

player_lookup = (
    dict(zip(data["players"]["player_id"], data["players"]["player_name"]))
    if not data["players"].empty
    else {}
)

picks_df = data.get("picks", pd.DataFrame())
pick_id_col = picks_df.columns[0] if not picks_df.empty else None
pick_choices = picks_df[pick_id_col].astype(str).tolist() if pick_id_col else []

c1, c2 = st.columns([2, 1])

with c1:
    selected_team_name = st.selectbox(
        "Selecione o time",
        teams["team_name"].tolist(),
        key="teams_selected_team_name_v1",
    )

with c2:
    selected_start_season = st.selectbox(
        "Temporada inicial",
        SEASONS,
        format_func=lambda x: SEASON_LABELS[x],
        key="teams_selected_start_season_v1",
    )

selected_team_id = int(
    teams.loc[teams["team_name"] == selected_team_name, "team_id"].iloc[0]
)
visible_seasons = get_visible_seasons(selected_start_season)

main_team_df = data["roster"].loc[data["roster"]["team_id"] == selected_team_id].copy()
dev_team_df = data["development"].loc[data["development"]["team_id"] == selected_team_id].copy()

main_roster_raw = build_roster_view(
    main_team_df, data["players"], selected_team_id, "MAIN", visible_seasons
)
main_roster = format_roster_for_display(main_roster_raw, visible_seasons)
main_totals = calculate_main_totals(main_team_df, data["fines"], selected_team_id, visible_seasons)

dev_roster_raw = build_roster_view(
    dev_team_df, data["players"], selected_team_id, "DEV", visible_seasons
)
dev_roster = format_roster_for_display(dev_roster_raw, visible_seasons)
dev_totals = calculate_dev_totals(dev_team_df, visible_seasons)

picks_team_df = build_picks_view(data["picks"], data["teams"], selected_team_id)
picks_display = format_picks_for_display(picks_team_df)

main_position_counts = summarize_positions(main_roster)
dev_position_counts = summarize_positions(dev_roster)

main_positions_text = " | ".join([f"{pos}: {qty}" for pos, qty in main_position_counts.items()]) if main_position_counts else "-"
dev_positions_text = " | ".join([f"{pos}: {qty}" for pos, qty in dev_position_counts.items()]) if dev_position_counts else "-"

team_picks_df = picks_df.loc[picks_df["current_team_owner_id"] == selected_team_id].copy() if not picks_df.empty else pd.DataFrame()
pick_year_counts = summarize_picks_by_year(team_picks_df)
picks_display = team_picks_df.copy()

transactions_df = data.get(TX_SHEET, pd.DataFrame())
transaction_items_df = data.get(TX_ITEMS_SHEET, pd.DataFrame())

team_transactions_df = build_transactions_history(
    transactions_df,
    transaction_items_df,
    selected_team_id,
    team_lookup,
    player_lookup,
)

if not picks_display.empty:
    if "original_team_pick_id" in picks_display.columns:
        picks_display["Time original"] = picks_display["original_team_pick_id"].map(team_lookup).fillna(
            picks_display["original_team_pick_id"]
        )

    if "current_team_owner_id" in picks_display.columns:
        picks_display["Time atual"] = picks_display["current_team_owner_id"].map(team_lookup).fillna(
            picks_display["current_team_owner_id"]
        )

    rename_map = {
        "pick_id": "Pick",
        "year": "Ano",
        "round": "Round",
    }
    picks_display = picks_display.rename(columns=rename_map)

main_summary = main_totals.iloc[0].to_dict() if not main_totals.empty else {}
total_picks = len(team_picks_df)

cap_remaining = pd.to_numeric(
    pd.Series([main_summary.get("Cap restante", 0.0)]),
    errors="coerce"
).iloc[0]

if pd.isna(cap_remaining):
    cap_remaining = 0.0

if cap_remaining < 0:
    cap_status = "🔴 Cap estourado"
elif cap_remaining <= 5000000:
    cap_status = "🟡 Cap apertado"
else:
    cap_status = "🟢 Cap confortável"

inject_summary_card_css()

row_1 = st.columns(3)
with row_1[0]:
    render_summary_card("Time", selected_team_name)

with row_1[1]:
    render_summary_card("MAIN players", len(main_roster))

with row_1[2]:
    render_summary_card("DEV players", len(dev_roster))

row_2 = st.columns(3)
with row_2[0]:
    render_summary_card("Salários MAIN", currency(main_summary.get("Salários", 0.0)))

with row_2[1]:
    render_summary_card("Cap restante", currency(cap_remaining))

with row_2[2]:
    render_summary_card("Picks", total_picks)

st.markdown(f"**Status do cap:** {cap_status}")
st.divider()

tab_main, tab_dev, tab_picks, tab_transactions = st.tabs(
    ["Principal", "Development", "Picks", "Transactions"]
)

with tab_main:
    c1, c2, c3, c4 = st.columns(4)
    if not main_totals.empty:
        current_main = main_totals.iloc[0].to_dict()
        c1.metric("Jogadores", len(main_roster))
        c2.metric("Salários", currency(current_main.get("Salários", 0.0)))
        c3.metric("Multas", currency(current_main.get("Multas", 0.0)))
        c4.metric("Cap restante", currency(current_main.get("Cap restante", 0.0)))

    st.caption(f"Posições: {main_positions_text}")

    display_main = build_red_flags(main_roster, visible_seasons)

    st.dataframe(
        display_main,
        use_container_width=True,
        hide_index=True,
        column_order=get_roster_column_order(display_main, visible_seasons),
        column_config=get_roster_column_config(visible_seasons),
    )

    with st.expander("Totalizadores do elenco principal", expanded=False):
        main_totals_display = main_totals.copy()
        for col in ["Salários", "Multas", "Cap restante"]:
            if col in main_totals_display.columns:
                main_totals_display[col] = main_totals_display[col].apply(currency)
        st.dataframe(main_totals_display, use_container_width=True, hide_index=True)

with tab_dev:
    c1, c2, c3 = st.columns(3)
    if not dev_totals.empty:
        current_dev = dev_totals.iloc[0].to_dict()
        c1.metric("Jogadores", len(dev_roster))
        c2.metric("Salários", currency(current_dev.get("Salários", 0.0)))
        c3.metric("Cap restante", currency(current_dev.get("Cap restante", 0.0)))

    st.caption(f"Posições: {dev_positions_text}")

    display_dev = build_red_flags(dev_roster, visible_seasons)

    st.dataframe(
        display_dev,
        use_container_width=True,
        hide_index=True,
        column_order=get_roster_column_order(display_dev, visible_seasons),
        column_config=get_roster_column_config(visible_seasons),
    )

    with st.expander("Totalizadores da development", expanded=False):
        dev_totals_display = dev_totals.copy()
        for col in ["Salários", "Cap restante"]:
            if col in dev_totals_display.columns:
                dev_totals_display[col] = dev_totals_display[col].apply(currency)
        st.dataframe(dev_totals_display, use_container_width=True, hide_index=True)

with tab_picks:
    total_picks = len(team_picks_df)

    if team_picks_df.empty:
        st.info("Esse time não possui picks cadastradas.")
    else:
        metric_cols = st.columns(len(pick_year_counts) + 1 if pick_year_counts else 1)
        metric_cols[0].metric("Total de picks", total_picks)

        for idx, (year, qty) in enumerate(sorted(pick_year_counts.items()), start=1):
            metric_cols[idx].metric(str(year), qty)

        st.dataframe(
            picks_display,
            use_container_width=True,
            hide_index=True,
            column_order=get_picks_column_order(picks_display),
            column_config=get_picks_column_config(),
        )

with tab_transactions:
    if is_admin:
        with st.expander("Registrar nova transaction", expanded=False):
            tx_base_df = data.get(TX_SHEET, pd.DataFrame())
            transaction_items_df = data.get(TX_ITEMS_SHEET, pd.DataFrame())

            team_options = teams["team_name"].tolist()
            team_name_to_id = dict(zip(teams["team_name"], teams["team_id"]))

            tx_type = st.selectbox(
                "Tipo de transaction",
                ["TRADE", "WAIVER", "FREE AGENT", "OTHER"],
                key="tx_type_v4",
            )
            tx_season = st.selectbox(
                "Season",
                SEASONS,
                format_func=lambda x: SEASON_LABELS[x],
                key="tx_season_v4",
            )

            col_a, col_b = st.columns(2)

            with col_a:
                from_team_name = st.selectbox("Time A", team_options, key="tx_from_team_v4")

            with col_b:
                available_to_teams = [t for t in team_options if t != from_team_name]
                to_team_name = st.selectbox("Time B", available_to_teams, key="tx_to_team_v4")

            from_team_id = int(team_name_to_id[from_team_name])
            to_team_id = int(team_name_to_id[to_team_name])

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
                tx_status = st.selectbox(
                    "Status",
                    ["PENDING", "APPROVED", "DONE"],
                    index=2,
                    key="tx_status_v4",
                )

            tx_notes = st.text_area("Observações", key="tx_notes_v4")

            st.markdown(f"### Assets enviados por {from_team_name}")

            from_side_count = st.number_input(
                f"Quantidade de assets enviados por {from_team_name}",
                min_value=0,
                max_value=10,
                value=1,
                step=1,
                key="from_side_count_v4",
            )

            from_side_items = []

            for i in range(int(from_side_count)):
                st.markdown(f"**Item {i+1} - {from_team_name}**")
                c1, c2, c3 = st.columns(3)

                with c1:
                    item_type = st.selectbox(
                        "Tipo",
                        ["player", "pick"],
                        key=f"from_item_type_{i}",
                    )

                with c2:
                    if item_type == "player":
                        roster_type = st.selectbox(
                            "Origem do jogador",
                            ["MAIN", "DEV"],
                            key=f"from_roster_type_{i}",
                        )
                    else:
                        roster_type = None
                        st.selectbox(
                            "Origem do jogador",
                            ["-"],
                            key=f"from_roster_type_placeholder_{i}",
                            disabled=True,
                        )

                if item_type == "player":
                    if roster_type == "MAIN":
                        source_df = data["roster"].loc[data["roster"]["team_id"] == from_team_id].copy()
                    else:
                        source_df = data["development"].loc[data["development"]["team_id"] == from_team_id].copy()

                    player_ids = source_df["player_id"].dropna().astype(int).tolist() if not source_df.empty else []
                    player_labels = {int(pid): player_lookup.get(int(pid), str(pid)) for pid in player_ids}

                    with c3:
                        selected_asset = (
                            st.selectbox(
                                "Jogador",
                                options=player_ids,
                                format_func=lambda x: player_labels.get(x, str(x)),
                                key=f"from_asset_player_{i}",
                            )
                            if player_ids
                            else st.selectbox(
                                "Jogador",
                                options=[None],
                                format_func=lambda x: "Sem jogadores disponíveis",
                                key=f"from_asset_player_empty_{i}",
                            )
                        )
                else:
                    team_pick_ids = pick_domain_ids(data, from_team_id)
                    pick_options = sorted(team_pick_ids)

                    with c3:
                        selected_asset = (
                            st.selectbox(
                                "Pick",
                                options=pick_options,
                                key=f"from_asset_pick_{i}",
                            )
                            if pick_options
                            else st.selectbox(
                                "Pick",
                                options=[None],
                                format_func=lambda x: "Sem picks disponíveis",
                                key=f"from_asset_pick_empty_{i}",
                            )
                        )

                target_roster_type = (
                    "MAIN" if item_type == "player" and roster_type == "MAIN"
                    else "DEV" if item_type == "player" and roster_type == "DEV"
                    else None
                )

                from_side_items.append({
                    "item_id": i + 1,
                    "item_type": item_type,
                    "asset_id": selected_asset,
                    "from_team_id": from_team_id,
                    "to_team_id": to_team_id,
                    "from_roster_type": roster_type,
                    "to_roster_type": target_roster_type,
                })

            st.markdown(f"### Assets enviados por {to_team_name}")

            to_side_count = st.number_input(
                f"Quantidade de assets enviados por {to_team_name}",
                min_value=0,
                max_value=10,
                value=1,
                step=1,
                key="to_side_count_v4",
            )

            to_side_items = []

            for i in range(int(to_side_count)):
                st.markdown(f"**Item {i+1} - {to_team_name}**")
                c1, c2, c3 = st.columns(3)

                with c1:
                    item_type = st.selectbox(
                        "Tipo",
                        ["player", "pick"],
                        key=f"to_item_type_{i}",
                    )

                with c2:
                    if item_type == "player":
                        roster_type = st.selectbox(
                            "Origem do jogador",
                            ["MAIN", "DEV"],
                            key=f"to_roster_type_{i}",
                        )
                    else:
                        roster_type = None
                        st.selectbox(
                            "Origem do jogador",
                            ["-"],
                            key=f"to_roster_type_placeholder_{i}",
                            disabled=True,
                        )

                if item_type == "player":
                    if roster_type == "MAIN":
                        source_df = data["roster"].loc[data["roster"]["team_id"] == to_team_id].copy()
                    else:
                        source_df = data["development"].loc[data["development"]["team_id"] == to_team_id].copy()

                    player_ids = source_df["player_id"].dropna().astype(int).tolist() if not source_df.empty else []
                    player_labels = {int(pid): player_lookup.get(int(pid), str(pid)) for pid in player_ids}

                    with c3:
                        selected_asset = (
                            st.selectbox(
                                "Jogador",
                                options=player_ids,
                                format_func=lambda x: player_labels.get(x, str(x)),
                                key=f"to_asset_player_{i}",
                            )
                            if player_ids
                            else st.selectbox(
                                "Jogador",
                                options=[None],
                                format_func=lambda x: "Sem jogadores disponíveis",
                                key=f"to_asset_player_empty_{i}",
                            )
                        )
                else:
                    team_pick_ids = pick_domain_ids(data, to_team_id)
                    pick_options = sorted(team_pick_ids)

                    with c3:
                        selected_asset = (
                            st.selectbox(
                                "Pick",
                                options=pick_options,
                                key=f"to_asset_pick_{i}",
                            )
                            if pick_options
                            else st.selectbox(
                                "Pick",
                                options=[None],
                                format_func=lambda x: "Sem picks disponíveis",
                                key=f"to_asset_pick_empty_{i}",
                            )
                        )

                target_roster_type = (
                    "MAIN" if item_type == "player" and roster_type == "MAIN"
                    else "DEV" if item_type == "player" and roster_type == "DEV"
                    else None
                )

                to_side_items.append({
                    "item_id": int(from_side_count) + i + 1,
                    "item_type": item_type,
                    "asset_id": selected_asset,
                    "from_team_id": to_team_id,
                    "to_team_id": from_team_id,
                    "from_roster_type": roster_type,
                    "to_roster_type": target_roster_type,
                })

            all_item_rows = from_side_items + to_side_items

            save_tx = st.button("Salvar transaction", type="primary", key="save_tx_v4")

            if save_tx:
                form_errors = []

                if from_team_id == to_team_id:
                    form_errors.append("Time A e Time B não podem ser iguais.")

                valid_item_rows = []
                for idx, row in enumerate(all_item_rows, start=1):
                    if row["asset_id"] in [None, "", "Sem jogadores disponíveis", "Sem picks disponíveis"]:
                        form_errors.append(f"Item {idx}: asset inválido.")
                    else:
                        valid_item_rows.append(row)

                if not valid_item_rows:
                    form_errors.append("A transaction precisa ter ao menos um asset válido.")

                validation_errors = validate_items_bilateral(data, valid_item_rows)
                form_errors.extend(validation_errors)

                if form_errors:
                    for err in form_errors:
                        st.error(err)
                else:
                    tx_id_col = "transaction_id" if "transaction_id" in tx_base_df.columns else "transactionid"
                    next_tx_id = get_next_id(tx_base_df, tx_id_col, start=1)

                    tx_row = {
                        tx_id_col: next_tx_id,
                        "transaction_date" if "transaction_date" in tx_base_df.columns else "transactiondate": str(tx_date),
                        "transaction_type" if "transaction_type" in tx_base_df.columns else "transactiontype": tx_type,
                        "season": tx_season,
                        "from_team_id" if "from_team_id" in tx_base_df.columns else "fromteamid": from_team_id,
                        "to_team_id" if "to_team_id" in tx_base_df.columns else "toteamid": to_team_id,
                        "initiated_by" if "initiated_by" in tx_base_df.columns else "initiatedby": initiated_by,
                        "status": tx_status,
                        "notes": tx_notes,
                    }

                    prepared_items = []
                    item_id_col = "item_id" if (not transaction_items_df.empty and "item_id" in transaction_items_df.columns) else "itemid"
                    transaction_id_col = "transaction_id" if (not transaction_items_df.empty and "transaction_id" in transaction_items_df.columns) else "transactionid"
                    item_type_col = "item_type" if (not transaction_items_df.empty and "item_type" in transaction_items_df.columns) else "itemtype"
                    asset_id_col = "asset_id" if (not transaction_items_df.empty and "asset_id" in transaction_items_df.columns) else "assetid"
                    from_rt_col = "from_roster_type" if (not transaction_items_df.empty and "from_roster_type" in transaction_items_df.columns) else "fromrostertype"
                    to_rt_col = "to_roster_type" if (not transaction_items_df.empty and "to_roster_type" in transaction_items_df.columns) else "torostertype"
                    from_team_col = "from_team_id" if (not transaction_items_df.empty and "from_team_id" in transaction_items_df.columns) else "fromteamid"
                    to_team_col = "to_team_id" if (not transaction_items_df.empty and "to_team_id" in transaction_items_df.columns) else "toteamid"

                    for row in valid_item_rows:
                        prepared_items.append({
                            transaction_id_col: next_tx_id,
                            item_id_col: row["item_id"],
                            item_type_col: row["item_type"],
                            asset_id_col: row["asset_id"],
                            from_rt_col: row["from_roster_type"],
                            to_rt_col: row["to_roster_type"],
                            from_team_col: row["from_team_id"],
                            to_team_col: row["to_team_id"],
                        })

                    append_transaction(str(DEFAULT_FILE), tx_row, prepared_items)
                    update_rosters(str(DEFAULT_FILE), tx_row, prepared_items)

                    st.cache_data.clear()
                    st.success("Transaction salva e aplicada com sucesso.")
                    st.rerun()

    st.subheader("Histórico de transactions")

    if team_transactions_df.empty:
        st.info("Esse time ainda não possui transactions registradas.")
    else:
        filter_col1, filter_col2, filter_col3 = st.columns(3)

        type_options = ["Todas"]
        if "transaction_type" in team_transactions_df.columns:
            type_options += sorted(
                team_transactions_df["transaction_type"].dropna().astype(str).unique().tolist()
            )

        status_options = ["Todos"]
        if "status" in team_transactions_df.columns:
            status_options += sorted(
                team_transactions_df["status"].dropna().astype(str).unique().tolist()
            )

        season_options = ["Todas"]
        if "season" in team_transactions_df.columns:
            season_options += sorted(
                team_transactions_df["season"].dropna().astype(str).unique().tolist()
            )

        with filter_col1:
            selected_tx_type = st.selectbox("Tipo", type_options, key="tx_history_type_v4")

        with filter_col2:
            selected_tx_status = st.selectbox("Status", status_options, key="tx_history_status_v4")

        with filter_col3:
            selected_tx_season = st.selectbox("Season", season_options, key="tx_history_season_v4")

        filtered_tx = team_transactions_df.copy()

        if selected_tx_type != "Todas" and "transaction_type" in filtered_tx.columns:
            filtered_tx = filtered_tx.loc[
                filtered_tx["transaction_type"].astype(str) == selected_tx_type
            ]

        if selected_tx_status != "Todos" and "status" in filtered_tx.columns:
            filtered_tx = filtered_tx.loc[
                filtered_tx["status"].astype(str) == selected_tx_status
            ]

        if selected_tx_season != "Todas" and "season" in filtered_tx.columns:
            filtered_tx = filtered_tx.loc[
                filtered_tx["season"].astype(str) == selected_tx_season
            ]

        metric_cols = st.columns(3)
        metric_cols[0].metric("Transactions", len(filtered_tx))
        metric_cols[1].metric(
            "Tipos distintos",
            filtered_tx["transaction_type"].nunique() if "transaction_type" in filtered_tx.columns else 0,
        )
        metric_cols[2].metric(
            "Seasons",
            filtered_tx["season"].nunique() if "season" in filtered_tx.columns else 0,
        )

        st.dataframe(filtered_tx, use_container_width=True, hide_index=True)

    if not is_admin:
        st.caption("Somente administradores podem criar, editar ou cancelar transactions.")