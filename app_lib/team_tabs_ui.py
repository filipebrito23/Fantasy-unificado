from __future__ import annotations

import pandas as pd
import streamlit as st
from app_lib.transforms import SEASON_LABELS
from app_lib.teams_ui_helpers import (
    currency,
    get_picks_column_order,
    get_picks_column_config,
)

POSITION_ORDER = {
    "PG": 0,
    "PG/SG": 1,
    "SG": 2,
    "SG/SF": 3,
    "SF": 4,
    "SF/PF": 5,
    "PF": 6,
    "PF/C": 7,
    "C": 8,
}


def _prepare_main_display(df: pd.DataFrame) -> pd.DataFrame:
    if df.empty or "Posição" not in df.columns:
        return df
    out = df.copy()
    out["__pos_order__"] = out["Posição"].map(POSITION_ORDER).fillna(999).astype(int)
    return out.sort_values(["__pos_order__", "Jogador"], kind="stable").drop(columns=["__pos_order__"])


def _compact_team_columns(df: pd.DataFrame) -> dict:
    return {
        "Ordem": None,
        "Jogador": st.column_config.TextColumn("Jogador", width="small"),
        "Posição": st.column_config.TextColumn("Posição", width="small"),
    }

def _format_salary_columns(
    df: pd.DataFrame,
    visible_seasons: list[str],
) -> pd.DataFrame:
    out = df.copy()

    for season in visible_seasons:
        column = f"Salário {season}"

        if column in out.columns:
            out[column] = out[column].map(
                lambda value: (
                    f"US$ {float(value):,.2f}"
                    if pd.notna(value)
                    else ""
                )
            )

    return out

def render_main_tab(page_context: dict) -> None:
    main_roster = page_context["main_roster"]
    visible_seasons = page_context["visible_seasons"]
    main_positions_text = page_context["main_positions_text"]
    totals_by_season = page_context["totals_by_season"]

    display_main = _prepare_main_display(
        page_context["display_main"]
    )

    display_main = _format_salary_columns(
        display_main,
        visible_seasons,
    )

    c1, c2, c3, c4, c5 = st.columns(5)

    first_season = visible_seasons[0]
    first_totals = totals_by_season[
        first_season
    ]["main"]

    if not first_totals.empty:
        current_main = first_totals.iloc[0].to_dict()

        c1.metric(
            "Jogadores",
            len(main_roster),
        )

        c2.metric(
            "Salários",
            currency(
                current_main.get(
                    "Salários",
                    0.0,
                )
            ),
        )

        c3.metric(
            "Multas",
            currency(
                current_main.get(
                    "Multas",
                    0.0,
                )
            ),
        )

        c4.metric(
            "Disponível",
            currency(
                current_main.get(
                    "Disponível",
                    0.0,
                )
            ),
        )

        c5.metric(
            "Cap restante",
            currency(
                current_main.get(
                    "Cap restante",
                    0.0,
                )
            ),
        )

    st.caption(
        f"Posições: {main_positions_text}"
    )

    roster_column_order = [
        "Jogador",
        "Posição",
    ]

    for season in visible_seasons:
        roster_column_order.extend(
            [
                f"Salário {season}",
                f"Option {season}",
            ]
        )

    roster_column_order = [
        column
        for column in roster_column_order
        if column in display_main.columns
    ]

    roster_column_config = {
        "Jogador": st.column_config.TextColumn(
            "Jogador",
            width="medium",
        ),
        "Posição": st.column_config.TextColumn(
            "Posição",
            width="small",
        ),
    }

    for season in visible_seasons:
        salary_column = f"Salário {season}"
        option_column = f"Option {season}"

        if salary_column in display_main.columns:
            roster_column_config[salary_column] = (
                st.column_config.NumberColumn(
                    SEASON_LABELS.get(
                        season,
                        season,
                    ),
                    format="Text",
                    disabled=True,
                )
            )

        if option_column in display_main.columns:
            roster_column_config[option_column] = (
                st.column_config.CheckboxColumn(
                    "Option",
                    disabled=True,
                )
            )

    st.dataframe(
        display_main,
        use_container_width=True,
        hide_index=True,
        column_order=roster_column_order,
        column_config=roster_column_config,
    )

    with st.expander(
        "Totalizadores do elenco principal",
        expanded=True,
    ):
        totals_frames = []

        for season in visible_seasons:
            season_totals = totals_by_season[
                season
            ]["main"].copy()

            if not season_totals.empty:
                totals_frames.append(
                    season_totals
                )

        if totals_frames:
            main_totals_display = pd.concat(
                totals_frames,
                ignore_index=True,
            )

            for column in [
                "Salários",
                "Multas",
                "Disponível",
                "Cap restante",
            ]:
                if column in main_totals_display.columns:
                    main_totals_display[column] = (
                        main_totals_display[column]
                        .map(currency)
                    )

            st.dataframe(
                main_totals_display,
                use_container_width=True,
                hide_index=True,
            )
        else:
            st.info(
                "Não há totalizadores para exibir."
            )


def render_dev_tab(page_context: dict) -> None:
    dev_roster = page_context["dev_roster"]
    visible_seasons = page_context["visible_seasons"]
    dev_positions_text = page_context["dev_positions_text"]
    totals_by_season = page_context["totals_by_season"]

    display_dev = page_context["display_dev"].copy()

    display_dev = _format_salary_columns(
    display_dev,
    visible_seasons,)

    c1, c2, c3 = st.columns(3)

    first_season = visible_seasons[0]
    first_totals = totals_by_season[
        first_season
    ]["dev"]

    if not first_totals.empty:
        current_dev = first_totals.iloc[0].to_dict()

        c1.metric(
            "Jogadores",
            len(dev_roster),
        )

        c2.metric(
            "Salários",
            currency(
                current_dev.get(
                    "Salários",
                    0.0,
                )
            ),
        )

        c3.metric(
            "Disponível",
            currency(
                current_dev.get(
                    "Disponível",
                    0.0,
                )
            ),
        )

    st.caption(
        f"Posições: {dev_positions_text}"
    )

    roster_column_order = [
        "Jogador",
        "Posição",
    ]

    for season in visible_seasons:
        roster_column_order.extend(
            [
                f"Salário {season}",
                f"Option {season}",
            ]
        )

    roster_column_order = [
        column
        for column in roster_column_order
        if column in display_dev.columns
    ]

    roster_column_config = {
        "Jogador": st.column_config.TextColumn(
            "Jogador",
            width="medium",
        ),
        "Posição": st.column_config.TextColumn(
            "Posição",
            width="small",
        ),
    }

    for season in visible_seasons:
        salary_column = f"Salário {season}"
        option_column = f"Option {season}"

        if salary_column in display_dev.columns:
            roster_column_config[salary_column] = (
                st.column_config.TextColumn(
                    SEASON_LABELS.get(
                        season,
                        season,
                    ),
                        width="medium",
                    )
            )

        if option_column in display_dev.columns:
            roster_column_config[option_column] = (
                st.column_config.CheckboxColumn(
                    "Option",
                    disabled=True,
                )
            )

    st.dataframe(
        display_dev,
        use_container_width=True,
        hide_index=True,
        column_order=roster_column_order,
        column_config=roster_column_config,
    )

    with st.expander(
        "Totalizadores de desenvolvimento",
        expanded=True,
    ):
        totals_frames = []

        for season in visible_seasons:
            season_totals = totals_by_season[
                season
            ]["dev"].copy()

            if not season_totals.empty:
                totals_frames.append(
                    season_totals
                )

        if totals_frames:
            dev_totals_display = pd.concat(
                totals_frames,
                ignore_index=True,
            )

            dev_totals_display = (
                dev_totals_display.drop(
                    columns=[
                        "Multas",
                        "Cap restante",
                    ],
                    errors="ignore",
                )
            )

            for column in [
                "Salários",
                "Disponível",
            ]:
                if column in dev_totals_display.columns:
                    dev_totals_display[column] = (
                        dev_totals_display[column]
                        .map(currency)
                    )

            st.dataframe(
                dev_totals_display,
                use_container_width=True,
                hide_index=True,
            )
        else:
            st.info(
                "Não há totalizadores para exibir."
            )

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
        column_config={
            **{
                "Pick": st.column_config.TextColumn("Pick", width="small"),
                "Ano": st.column_config.NumberColumn("Ano", width="small", format="%d"),
                "Round": st.column_config.NumberColumn("Round", width="small", format="%d"),
                "Time original": st.column_config.TextColumn("Time original", width="medium"),
                "Time atual": st.column_config.TextColumn("Time atual", width="medium"),
            },
            **get_picks_column_config(),
        },
    )