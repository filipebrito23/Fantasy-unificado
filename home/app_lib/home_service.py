import pandas as pd
from sqlalchemy import text

from app_lib.db_v5 import engine


def _df(result):
    return pd.DataFrame(result.fetchall(), columns=result.keys())


def get_home_tabs():
    with engine.begin() as conn:
        result = conn.execute(
            text(
                """
                SELECT tab_key, tab_label, is_active, sort_order, allow_posts, allow_comments
                FROM home_tabs
                WHERE is_active IS TRUE
                ORDER BY sort_order, tab_label
                """
            )
        )
        return _df(result)


def ensure_default_home_tabs():
    defaults = [
        ("regras", "Regras", True, 1, True, True),
        ("calendario", "Calendário", True, 2, True, True),
        ("draft", "Draft", True, 3, True, True),
        ("trades", "Trades", True, 4, True, True),
        ("dev", "Dev", True, 5, True, True),
        ("dispensas", "Dispensas", True, 6, True, True),
        ("jogos", "Jogos", True, 7, True, True),
        ("links", "Links", True, 8, True, True),
    ]

    with engine.begin() as conn:
        for row in defaults:
            conn.execute(
                text(
                    """
                    INSERT INTO home_tabs (
                        tab_key,
                        tab_label,
                        is_active,
                        sort_order,
                        allow_posts,
                        allow_comments
                    )
                    SELECT
                        :tab_key,
                        :tab_label,
                        :is_active,
                        :sort_order,
                        :allow_posts,
                        :allow_comments
                    WHERE NOT EXISTS (
                        SELECT 1
                        FROM home_tabs
                        WHERE tab_key = :tab_key
                    )
                    """
                ),
                {
                    "tab_key": row[0],
                    "tab_label": row[1],
                    "is_active": row[2],
                    "sort_order": row[3],
                    "allow_posts": row[4],
                    "allow_comments": row[5],
                },
            )


def get_active_rule():
    with engine.begin() as conn:
        result = conn.execute(
            text(
                """
                SELECT rule_id, title, content_md, version, updated_at, updated_by, is_active
                FROM rules_documents
                WHERE is_active IS TRUE
                ORDER BY updated_at DESC
                LIMIT 1
                """
            )
        )
        return _df(result)


def get_calendar_events():
    with engine.begin() as conn:
        result = conn.execute(
            text(
                """
                SELECT event_id, title, category, start_date, end_date, season, status, notes
                FROM calendar_events
                ORDER BY start_date, end_date, title
                """
            )
        )
        return _df(result)


def get_draft_board():
    with engine.begin() as conn:
        result = conn.execute(
            text(
                """
                SELECT
                    draft_id,
                    season,
                    round,
                    pick_number,
                    original_team_id,
                    current_team_id,
                    selected_player,
                    selected_player_id,
                    status,
                    notes
                FROM draft_board
                ORDER BY season, round, pick_number
                """
            )
        )
        return _df(result)


def get_links_by_section(section: str):
    with engine.begin() as conn:
        result = conn.execute(
            text(
                """
                SELECT link_id, section, label, url, description, is_active, sort_order
                FROM link_items
                WHERE lower(section) = lower(:section)
                  AND is_active IS TRUE
                ORDER BY sort_order, label
                """
            ),
            {"section": section},
        )
        return _df(result)


def get_posts_by_tab(tab_key: str):
    with engine.begin() as conn:
        result = conn.execute(
            text(
                """
                SELECT
                    post_id,
                    tab_key,
                    author,
                    title,
                    content_md,
                    status,
                    is_pinned,
                    created_at,
                    updated_at
                FROM home_posts
                WHERE lower(tab_key) = lower(:tab_key)
                  AND upper(status) = 'PUBLISHED'
                ORDER BY is_pinned DESC, created_at DESC
                """
            ),
            {"tab_key": tab_key},
        )
        return _df(result)


def create_post(
    tab_key: str,
    author: str,
    title: str,
    content_md: str,
    is_pinned: bool = False,
):
    with engine.begin() as conn:
        conn.execute(
            text(
                """
                INSERT INTO home_posts (
                    tab_key,
                    author,
                    title,
                    content_md,
                    status,
                    is_pinned
                )
                VALUES (
                    :tab_key,
                    :author,
                    :title,
                    :content_md,
                    'PUBLISHED',
                    :is_pinned
                )
                """
            ),
            {
                "tab_key": tab_key,
                "author": author,
                "title": title,
                "content_md": content_md,
                "is_pinned": is_pinned,
            },
        )


def get_comments(tab_key: str, post_id=None):
    sql = """
        SELECT
            comment_id,
            tab_key,
            post_id,
            author,
            comment_text,
            related_pick_id,
            status,
            created_at,
            is_pinned
        FROM wall_comments
        WHERE lower(tab_key) = lower(:tab_key)
          AND upper(status) = 'VISIBLE'
    """
    params = {"tab_key": tab_key}

    if post_id is None:
        sql += " AND post_id IS NULL "
    else:
        sql += " AND post_id = :post_id "
        params["post_id"] = post_id

    sql += " ORDER BY is_pinned DESC, created_at DESC "

    with engine.begin() as conn:
        result = conn.execute(text(sql), params)
        return _df(result)


def create_comment(
    tab_key: str,
    author: str,
    comment_text: str,
    post_id=None,
    related_pick_id=None,
    is_pinned: bool = False,
):
    with engine.begin() as conn:
        conn.execute(
            text(
                """
                INSERT INTO wall_comments (
                    tab_key,
                    post_id,
                    author,
                    comment_text,
                    related_pick_id,
                    status,
                    is_pinned
                )
                VALUES (
                    :tab_key,
                    :post_id,
                    :author,
                    :comment_text,
                    :related_pick_id,
                    'VISIBLE',
                    :is_pinned
                )
                """
            ),
            {
                "tab_key": tab_key,
                "post_id": post_id,
                "author": author,
                "comment_text": comment_text,
                "related_pick_id": related_pick_id,
                "is_pinned": is_pinned,
            },
        )