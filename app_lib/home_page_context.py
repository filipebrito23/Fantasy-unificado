from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import pandas as pd
import streamlit as st

from app_lib.home_service import (
    ensure_default_home_tabs,
    get_active_rule,
    get_calendar_events,
    get_comments,
    get_draft_board,
    get_home_tabs,
    get_links_by_section,
    get_posts_by_tab,
)


@dataclass
class HomePageContext:
    tabs_df: pd.DataFrame
    active_rule_df: pd.DataFrame
    calendar_df: pd.DataFrame
    draft_df: pd.DataFrame
    links_by_section: dict[str, pd.DataFrame]
    user: Any
    user_label: str
    is_admin: bool


@st.cache_data(show_spinner=False)
def _cached_home_core():
    ensure_default_home_tabs()
    tabs_df = get_home_tabs()
    active_rule_df = get_active_rule()
    calendar_df = get_calendar_events()
    draft_df = get_draft_board()
    links_by_section = {
        "jogos": get_links_by_section("jogos"),
        "links": get_links_by_section("links"),
    }
    return tabs_df, active_rule_df, calendar_df, draft_df, links_by_section


@st.cache_data(show_spinner=False)
def _cached_tab_posts(tab_key: str):
    return get_posts_by_tab(tab_key)


@st.cache_data(show_spinner=False)
def _cached_tab_comments(tab_key: str):
    return get_comments(tab_key)


def build_home_page_context(user: Any, user_label: str, is_admin: bool) -> HomePageContext:
    tabs_df, active_rule_df, calendar_df, draft_df, links_by_section = _cached_home_core()
    return HomePageContext(
        tabs_df=tabs_df,
        active_rule_df=active_rule_df,
        calendar_df=calendar_df,
        draft_df=draft_df,
        links_by_section=links_by_section,
        user=user,
        user_label=user_label,
        is_admin=is_admin,
    )


def get_tab_posts(tab_key: str) -> pd.DataFrame:
    return _cached_tab_posts(tab_key)


def get_tab_comments(tab_key: str) -> pd.DataFrame:
    return _cached_tab_comments(tab_key)