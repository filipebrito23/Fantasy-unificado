from pathlib import Path
import pandas as pd
from sqlalchemy import text
from app_lib.db_v5 import engine, init_db_v5


BASE_DIR = Path(__file__).resolve().parent
DEFAULT_XLSX = BASE_DIR / "blog.xlsx"


def normalize_columns(df: pd.DataFrame) -> pd.DataFrame:
    out = df.copy()
    out.columns = [str(c).strip().lower() for c in out.columns]
    return out


def clean_df(df: pd.DataFrame) -> pd.DataFrame:
    if df is None or df.empty:
        return pd.DataFrame()

    out = normalize_columns(df)
    out = out.dropna(how="all").copy()

    for col in out.columns:
        if out[col].dtype == object:
            out[col] = out[col].apply(lambda x: x.strip() if isinstance(x, str) else x)

    return out


def to_bool(value, default=False):
    if pd.isna(value):
        return default
    if isinstance(value, bool):
        return value
    txt = str(value).strip().lower()
    if txt in {"1", "true", "t", "yes", "y", "sim"}:
        return True
    if txt in {"0", "false", "f", "no", "n", "nao", "não"}:
        return False
    return default


def to_int_or_none(value):
    if pd.isna(value) or value == "":
        return None
    try:
        return int(float(value))
    except Exception:
        return None


def to_str_or_none(value):
    if pd.isna(value):
        return None
    txt = str(value).strip()
    return txt if txt else None


def parse_datetime_like(value):
    if pd.isna(value) or value == "":
        return None
    try:
        ts = pd.to_datetime(value)
        if pd.isna(ts):
            return None
        return ts.to_pydatetime()
    except Exception:
        return None


def parse_date_like(value):
    dt = parse_datetime_like(value)
    return dt.date() if dt else None


def read_sheet(xlsx_path: Path, sheet_name: str) -> pd.DataFrame:
    try:
        df = pd.read_excel(xlsx_path, sheet_name=sheet_name)
        return clean_df(df)
    except Exception:
        return pd.DataFrame()


def import_config_tabs(conn, df: pd.DataFrame):
    if df.empty:
        return

    for _, row in df.iterrows():
        tab_key = to_str_or_none(row.get("tab_key"))
        if not tab_key:
            continue

        conn.execute(text("""
            DELETE FROM home_tabs WHERE tab_key = :tab_key
        """), {"tab_key": tab_key})

        conn.execute(text("""
            INSERT INTO home_tabs (
                tab_key, tab_label, is_active, sort_order, allow_posts, allow_comments
            ) VALUES (
                :tab_key, :tab_label, :is_active, :sort_order, :allow_posts, :allow_comments
            )
        """), {
            "tab_key": tab_key,
            "tab_label": to_str_or_none(row.get("tab_label")) or tab_key.title(),
            "is_active": to_bool(row.get("is_active"), True),
            "sort_order": to_int_or_none(row.get("sort_order")) or 0,
            "allow_posts": to_bool(row.get("allow_posts"), True),
            "allow_comments": to_bool(row.get("allow_comments"), True),
        })


def import_regras(conn, df: pd.DataFrame):
    if df.empty:
        return

    for _, row in df.iterrows():
        rule_id = to_int_or_none(row.get("rule_id"))
        title = to_str_or_none(row.get("title"))
        content_md = to_str_or_none(row.get("content_md"))

        if not title or not content_md:
            continue

        if rule_id is not None:
            conn.execute(text("DELETE FROM rules_documents WHERE rule_id = :rule_id"), {"rule_id": rule_id})

        if rule_id is None:
            conn.execute(text("""
                INSERT INTO rules_documents (
                    title, content_md, version, updated_at, updated_by, is_active
                ) VALUES (
                    :title, :content_md, :version, :updated_at, :updated_by, :is_active
                )
            """), {
                "title": title,
                "content_md": content_md,
                "version": to_str_or_none(row.get("version")),
                "updated_at": parse_datetime_like(row.get("updated_at")),
                "updated_by": to_str_or_none(row.get("updated_by")),
                "is_active": to_bool(row.get("is_active"), True),
            })
        else:
            conn.execute(text("""
                INSERT INTO rules_documents (
                    rule_id, title, content_md, version, updated_at, updated_by, is_active
                ) VALUES (
                    :rule_id, :title, :content_md, :version, :updated_at, :updated_by, :is_active
                )
            """), {
                "rule_id": rule_id,
                "title": title,
                "content_md": content_md,
                "version": to_str_or_none(row.get("version")),
                "updated_at": parse_datetime_like(row.get("updated_at")),
                "updated_by": to_str_or_none(row.get("updated_by")),
                "is_active": to_bool(row.get("is_active"), True),
            })


def import_calendario(conn, df: pd.DataFrame):
    if df.empty:
        return

    for _, row in df.iterrows():
        event_id = to_int_or_none(row.get("event_id"))
        title = to_str_or_none(row.get("title"))
        category = to_str_or_none(row.get("category"))

        if not title or not category:
            continue

        if event_id is not None:
            conn.execute(text("DELETE FROM calendar_events WHERE event_id = :event_id"), {"event_id": event_id})

        payload = {
            "event_id": event_id,
            "title": title,
            "category": category,
            "start_date": parse_date_like(row.get("start_date")),
            "end_date": parse_date_like(row.get("end_date")),
            "season": to_str_or_none(row.get("season")),
            "status": to_str_or_none(row.get("status")),
            "notes": to_str_or_none(row.get("notes")),
        }

        if event_id is None:
            conn.execute(text("""
                INSERT INTO calendar_events (
                    title, category, start_date, end_date, season, status, notes
                ) VALUES (
                    :title, :category, :start_date, :end_date, :season, :status, :notes
                )
            """), payload)
        else:
            conn.execute(text("""
                INSERT INTO calendar_events (
                    event_id, title, category, start_date, end_date, season, status, notes
                ) VALUES (
                    :event_id, :title, :category, :start_date, :end_date, :season, :status, :notes
                )
            """), payload)


def import_draft_board(conn, df: pd.DataFrame):
    if df.empty:
        return

    for _, row in df.iterrows():
        draft_id = to_int_or_none(row.get("draft_id"))
        season = to_str_or_none(row.get("season"))
        round_ = to_int_or_none(row.get("round"))
        pick_number = to_int_or_none(row.get("pick_number"))

        if not season or round_ is None or pick_number is None:
            continue

        if draft_id is not None:
            conn.execute(text("DELETE FROM draft_board WHERE draft_id = :draft_id"), {"draft_id": draft_id})

        payload = {
            "draft_id": draft_id,
            "season": season,
            "round": round_,
            "pick_number": pick_number,
            "original_team_id": to_int_or_none(row.get("original_team_id")),
            "current_team_id": to_int_or_none(row.get("current_team_id")),
            "selected_player": to_str_or_none(row.get("selected_player")),
            "selected_player_id": to_int_or_none(row.get("selected_player_id")),
            "status": to_str_or_none(row.get("status")) or "OPEN",
            "notes": to_str_or_none(row.get("notes")),
        }

        if draft_id is None:
            conn.execute(text("""
                INSERT INTO draft_board (
                    season, round, pick_number, original_team_id, current_team_id,
                    selected_player, selected_player_id, status, notes
                ) VALUES (
                    :season, :round, :pick_number, :original_team_id, :current_team_id,
                    :selected_player, :selected_player_id, :status, :notes
                )
            """), payload)
        else:
            conn.execute(text("""
                INSERT INTO draft_board (
                    draft_id, season, round, pick_number, original_team_id, current_team_id,
                    selected_player, selected_player_id, status, notes
                ) VALUES (
                    :draft_id, :season, :round, :pick_number, :original_team_id, :current_team_id,
                    :selected_player, :selected_player_id, :status, :notes
                )
            """), payload)


def import_links(conn, df: pd.DataFrame):
    if df.empty:
        return

    for _, row in df.iterrows():
        link_id = to_int_or_none(row.get("link_id"))
        section = to_str_or_none(row.get("section"))
        label = to_str_or_none(row.get("label"))
        url = to_str_or_none(row.get("url"))

        if not section or not label or not url:
            continue

        if link_id is not None:
            conn.execute(text("DELETE FROM link_items WHERE link_id = :link_id"), {"link_id": link_id})

        payload = {
            "link_id": link_id,
            "section": section,
            "label": label,
            "url": url,
            "description": to_str_or_none(row.get("description")),
            "is_active": to_bool(row.get("is_active"), True),
            "sort_order": to_int_or_none(row.get("sort_order")) or 0,
        }

        if link_id is None:
            conn.execute(text("""
                INSERT INTO link_items (
                    section, label, url, description, is_active, sort_order
                ) VALUES (
                    :section, :label, :url, :description, :is_active, :sort_order
                )
            """), payload)
        else:
            conn.execute(text("""
                INSERT INTO link_items (
                    link_id, section, label, url, description, is_active, sort_order
                ) VALUES (
                    :link_id, :section, :label, :url, :description, :is_active, :sort_order
                )
            """), payload)


def import_posts(conn, df: pd.DataFrame):
    if df.empty:
        return

    for _, row in df.iterrows():
        post_id = to_int_or_none(row.get("post_id"))
        tab_key = to_str_or_none(row.get("tab_key"))
        author = to_str_or_none(row.get("author"))
        title = to_str_or_none(row.get("title"))
        content_md = to_str_or_none(row.get("content_md"))

        if not tab_key or not author or not title or not content_md:
            continue

        if post_id is not None:
            conn.execute(text("DELETE FROM home_posts WHERE post_id = :post_id"), {"post_id": post_id})

        payload = {
            "post_id": post_id,
            "tab_key": tab_key,
            "author": author,
            "title": title,
            "content_md": content_md,
            "status": to_str_or_none(row.get("status")) or "PUBLISHED",
            "is_pinned": to_bool(row.get("is_pinned"), False),
            "created_at": parse_datetime_like(row.get("created_at")),
            "updated_at": parse_datetime_like(row.get("updated_at")),
        }

        if post_id is None:
            conn.execute(text("""
                INSERT INTO home_posts (
                    tab_key, author, title, content_md, status, is_pinned, created_at, updated_at
                ) VALUES (
                    :tab_key, :author, :title, :content_md, :status, :is_pinned,
                    COALESCE(:created_at, CURRENT_TIMESTAMP),
                    COALESCE(:updated_at, CURRENT_TIMESTAMP)
                )
            """), payload)
        else:
            conn.execute(text("""
                INSERT INTO home_posts (
                    post_id, tab_key, author, title, content_md, status, is_pinned, created_at, updated_at
                ) VALUES (
                    :post_id, :tab_key, :author, :title, :content_md, :status, :is_pinned,
                    COALESCE(:created_at, CURRENT_TIMESTAMP),
                    COALESCE(:updated_at, CURRENT_TIMESTAMP)
                )
            """), payload)


def import_comments(conn, df: pd.DataFrame):
    if df.empty:
        return

    for _, row in df.iterrows():
        comment_id = to_int_or_none(row.get("comment_id"))
        tab_key = to_str_or_none(row.get("tab_key"))
        author = to_str_or_none(row.get("author"))
        comment_text = to_str_or_none(row.get("comment_text"))

        if not tab_key or not author or not comment_text:
            continue

        if comment_id is not None:
            conn.execute(text("DELETE FROM wall_comments WHERE comment_id = :comment_id"), {"comment_id": comment_id})

        payload = {
            "comment_id": comment_id,
            "tab_key": tab_key,
            "post_id": to_int_or_none(row.get("post_id")),
            "author": author,
            "comment_text": comment_text,
            "related_pick_id": to_int_or_none(row.get("related_pick_id")),
            "status": to_str_or_none(row.get("status")) or "VISIBLE",
            "created_at": parse_datetime_like(row.get("created_at")),
            "is_pinned": to_bool(row.get("is_pinned"), False),
        }

        if comment_id is None:
            conn.execute(text("""
                INSERT INTO wall_comments (
                    tab_key, post_id, author, comment_text, related_pick_id, status, created_at, is_pinned
                ) VALUES (
                    :tab_key, :post_id, :author, :comment_text, :related_pick_id, :status,
                    COALESCE(:created_at, CURRENT_TIMESTAMP), :is_pinned
                )
            """), payload)
        else:
            conn.execute(text("""
                INSERT INTO wall_comments (
                    comment_id, tab_key, post_id, author, comment_text, related_pick_id, status, created_at, is_pinned
                ) VALUES (
                    :comment_id, :tab_key, :post_id, :author, :comment_text, :related_pick_id, :status,
                    COALESCE(:created_at, CURRENT_TIMESTAMP), :is_pinned
                )
            """), payload)


def import_home_xlsx(xlsx_path: str | Path = DEFAULT_XLSX):
    xlsx_path = Path(xlsx_path)
    if not xlsx_path.exists():
        raise FileNotFoundError(f"Arquivo não encontrado: {xlsx_path}")

    init_db_v5()

    config_tabs_df = read_sheet(xlsx_path, "config_tabs")
    regras_df = read_sheet(xlsx_path, "regras")
    calendario_df = read_sheet(xlsx_path, "calendario")
    draft_board_df = read_sheet(xlsx_path, "draft_board")
    links_df = read_sheet(xlsx_path, "links")
    posts_df = read_sheet(xlsx_path, "posts")
    comments_df = read_sheet(xlsx_path, "comments")

    with engine.begin() as conn:
        import_config_tabs(conn, config_tabs_df)
        import_regras(conn, regras_df)
        import_calendario(conn, calendario_df)
        import_draft_board(conn, draft_board_df)
        import_links(conn, links_df)
        import_posts(conn, posts_df)
        import_comments(conn, comments_df)

    print(f"Importação concluída com sucesso: {xlsx_path}")


if __name__ == "__main__":
    import_home_xlsx()