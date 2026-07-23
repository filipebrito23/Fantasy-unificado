from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import pandas as pd

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
    posts_by_tab: dict[str, pd.DataFrame]
    comments_by_tab: dict[str, pd.DataFrame]
    links_by_section: dict[str, pd.DataFrame]
    user: Any
    user_label: str
    is_admin: bool


def build_home_page_context(user: Any, user_label: str, is_admin: bool) -> HomePageContext:
    ensure_default_home_tabs()
    tabs_df = get_home_tabs()

    posts_by_tab: dict[str, pd.DataFrame] = {}
    comments_by_tab: dict[str, pd.DataFrame] = {}
    for tab_key in tabs_df["tab_key"].tolist() if not tabs_df.empty and "tab_key" in tabs_df.columns else []:
        posts_by_tab[tab_key] = get_posts_by_tab(tab_key)
        comments_by_tab[tab_key] = get_comments(tab_key)

    links_by_section = {
        "jogos": get_links_by_section("jogos"),
        "links": get_links_by_section("links"),
    }

    return HomePageContext(
        tabs_df=tabs_df,
        active_rule_df=get_active_rule(),
        calendar_df=get_calendar_events(),
        draft_df=get_draft_board(),
        posts_by_tab=posts_by_tab,
        comments_by_tab=comments_by_tab,
        links_by_section=links_by_section,
        user=user,
        user_label=user_label,
        is_admin=is_admin,
    )