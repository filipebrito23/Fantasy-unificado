import streamlit as st

from app_lib.teams_ui_helpers import (
    currency,
    get_roster_column_order,
    get_roster_column_config,
    get_picks_column_order,
    get_picks_column_config,
)


def render_main_tab(page_context: dict) -> None:
    main_roster = page_context["main_roster"]
    main_totals = page_context["main_totals"]
    display_main = page_context["display_main"]
    visible_seasons = page_context["visible_seasons"]
    main_positions_text = page_context["main_positions_text"]

    c1, c2, c3, c4 = st.columns(4)
    if not main_totals.empty:
        current_main = main_totals.iloc[0].to_dict()
        c1.metric("Jogadores", len(main_roster))
        c2.metric("Salários", currency(current_main.get("Salários", 0.0)))
        c3.metric("Multas", currency(current_main.get("Multas", 0.0)))
        c4.metric("Cap restante", currency(current_main.get("Cap restante", 0.0)))

    st.caption(f"Posições: {main_positions_text}")

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


def render_dev_tab(page_context: dict) -> None:
    dev_roster = page_context["dev_roster"]
    dev_totals = page_context["dev_totals"]
    display_dev = page_context["display_dev"]
    visible_seasons = page_context["visible_seasons"]
    dev_positions_text = page_context["dev_positions_text"]

    c1, c2, c3 = st.columns(3)
    if not dev_totals.empty:
        current_dev = dev_totals.iloc[0].to_dict()
        c1.metric("Jogadores", len(dev_roster))
        c2.metric("Salários", currency(current_dev.get("Salários", 0.0)))
        c3.metric("Cap restante", currency(current_dev.get("Cap restante", 0.0)))

    st.caption(f"Posições: {dev_positions_text}")

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


def render_picks_tab(page_context: dict) -> None:
    team_picks_df = page_context["team_picks_df"]
    picks_display = page_context["picks_display"]
    pick_year_counts = page_context["pick_year_counts"]
    total_picks = page_context["total_picks"]

    if team_picks_df.empty:
        st.info("Esse time não possui picks cadastradas.")
        return

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