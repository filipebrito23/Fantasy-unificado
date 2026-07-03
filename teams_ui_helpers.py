# teams_ui_helpers.py

import pandas as pd
import streamlit as st

from transforms import SEASON_LABELS


def currency(v) -> str:
    if v is None or (isinstance(v, str) and not v.strip()):
        return "-"

    n = pd.to_numeric(pd.Series([v]), errors="coerce").iloc[0]

    if pd.isna(n):
        return str(v)

    return f"US$ {float(n):,.2f}"


def format_salary_columns(df: pd.DataFrame, visible_seasons: list[str]) -> pd.DataFrame:
    if df.empty:
        return df

    out = df.copy()
    for season in visible_seasons:
        label = SEASON_LABELS[season]
        if label in out.columns:
            out[label] = out[label].apply(currency)
    return out


def format_money_columns(df: pd.DataFrame, cols: list[str]) -> pd.DataFrame:
    if df.empty:
        return df

    out = df.copy()
    for col in cols:
        if col in out.columns:
            out[col] = out[col].apply(currency)
    return out


def display_table(df: pd.DataFrame):
    st.dataframe(df, use_container_width=True, hide_index=True)


def build_red_flags(df: pd.DataFrame, visible_seasons: list[str]) -> pd.DataFrame:
    if df.empty:
        return df

    out = df.copy()

    for season in visible_seasons:
        sal_col = SEASON_LABELS[season]
        opt_col = f"TO_{season}"

        if sal_col not in out.columns or opt_col not in out.columns:
            continue

        mask = out[opt_col].astype(str).str.strip().str.lower().eq("sim")
        out[sal_col] = out[sal_col].apply(currency)
        out.loc[mask, sal_col] = out.loc[mask, sal_col].astype(str) + " 🔴"

    to_cols = [f"TO_{season}" for season in visible_seasons if f"TO_{season}" in out.columns]
    out = out.drop(columns=to_cols, errors="ignore")

    return out


def format_totals(df: pd.DataFrame, money_cols: list[str]) -> pd.DataFrame:
    if df.empty:
        return df

    out = df.copy()
    for col in money_cols:
        if col in out.columns:
            out[col] = out[col].apply(currency)
    return out


def get_roster_column_order(df: pd.DataFrame, visible_seasons: list[str]) -> list[str]:
    ordered = ["Ordem", "Jogador", "Posição"]
    ordered += [
        SEASON_LABELS[season]
        for season in visible_seasons
        if SEASON_LABELS[season] in df.columns
    ]
    return [col for col in ordered if col in df.columns]


def get_roster_column_config(visible_seasons: list[str]) -> dict:
    config = {
        "Ordem": st.column_config.NumberColumn("Ordem", width="small", format="%d"),
        "Jogador": st.column_config.TextColumn("Jogador", width="large"),
        "Posição": st.column_config.TextColumn("Posição", width="small"),
    }

    for season in visible_seasons:
        label = SEASON_LABELS[season]
        config[label] = st.column_config.TextColumn(label, width="medium")

    return config


def get_picks_column_order(df: pd.DataFrame) -> list[str]:
    preferred = ["Pick", "Ano", "Round", "Time original", "Time atual"]
    return [col for col in preferred if col in df.columns]


def get_picks_column_config() -> dict:
    return {
        "Pick": st.column_config.TextColumn("Pick", width="medium"),
        "Ano": st.column_config.NumberColumn("Ano", width="small", format="%d"),
        "Round": st.column_config.NumberColumn("Round", width="small", format="%d"),
        "Time original": st.column_config.TextColumn("Time original", width="medium"),
        "Time atual": st.column_config.TextColumn("Time atual", width="medium"),
    }


def inject_summary_card_css():
    st.markdown("""
    <style>
    .summary-card {
        padding: 14px 16px;
        border-radius: 12px;
        background: rgba(127, 127, 127, 0.08);
        border: 1px solid rgba(127, 127, 127, 0.18);
        margin-bottom: 10px;
        min-height: 96px;
        display: flex;
        flex-direction: column;
        justify-content: center;
    }
    .summary-label {
        font-size: 0.82rem;
        opacity: 0.75;
        margin-bottom: 6px;
    }
    .summary-value {
        font-size: 1.35rem;
        font-weight: 700;
        line-height: 1.2;
    }
    .cap-status-line {
        margin-top: 0.35rem;
        margin-bottom: 0.35rem;
        font-size: 0.9rem;
        font-weight: 600;
    }
    </style>
    """, unsafe_allow_html=True)


def render_summary_card(label, value):
    st.markdown(
        f"""
        <div class="summary-card">
            <div class="summary-label">{label}</div>
            <div class="summary-value">{value}</div>
        </div>
        """,
        unsafe_allow_html=True,
    )