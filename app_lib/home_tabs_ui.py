from __future__ import annotations

from datetime import date

import pandas as pd
import streamlit as st

from app_lib.home_service import create_comment, create_post
from app_lib.home_page_context import HomePageContext


def render_empty_state(message: str):
    st.info(message)


def render_comments(tab_key: str, ctx: HomePageContext):
    st.markdown("#### Comentários")
    comments_df = ctx.comments_by_tab.get(tab_key, pd.DataFrame())

    if comments_df.empty:
        render_empty_state("Sem comentários ainda.")
    else:
        for _, row in comments_df.iterrows():
            pin = "📌 " if bool(row.get("is_pinned")) else ""
            st.markdown(f"**{pin}{row['author']}** — {row['created_at']}")
            st.write(row["comment_text"])
            st.divider()

    comment_text = st.text_area("Novo comentário", key=f"comment_box_{tab_key}")
    if st.button("Publicar comentário", key=f"comment_btn_{tab_key}"):
        if comment_text.strip():
            create_comment(
                tab_key=tab_key,
                author=ctx.user_label,
                comment_text=comment_text.strip(),
            )
            st.success("Comentário publicado.")
            st.rerun()
        else:
            st.error("Digite um comentário antes de publicar.")


def render_posts(tab_key: str, ctx: HomePageContext):
    posts_df = ctx.posts_by_tab.get(tab_key, pd.DataFrame())

    if not posts_df.empty:
        st.markdown("#### Posts")
        for _, row in posts_df.iterrows():
            pin = "📌 " if bool(row.get("is_pinned")) else ""
            st.markdown(f"### {pin}{row['title']}")
            st.caption(f"{row['author']} • {row['created_at']}")
            st.markdown(row["content_md"])
            st.divider()
    else:
        render_empty_state("Nenhum post cadastrado.")

    if ctx.is_admin:
        with st.form(f"post_form_{tab_key}", clear_on_submit=True):
            title = st.text_input("Título")
            content_md = st.text_area("Conteúdo", height=180)
            is_pinned = st.checkbox("Fixar post")
            submitted = st.form_submit_button("Publicar post")

        if submitted:
            if title.strip() and content_md.strip():
                create_post(
                    tab_key=tab_key,
                    author=ctx.user_label,
                    title=title.strip(),
                    content_md=content_md.strip(),
                    is_pinned=is_pinned,
                )
                st.success("Post criado.")
                st.rerun()
            else:
                st.error("Título e conteúdo são obrigatórios.")


def render_links_section(section_name: str, ctx: HomePageContext):
    links_df = ctx.links_by_section.get(section_name, pd.DataFrame())

    if links_df.empty:
        render_empty_state("Nenhum link cadastrado.")
        return

    for _, row in links_df.iterrows():
        st.markdown(f"- [{row['label']}]({row['url']})")
        if pd.notna(row.get("description")) and str(row.get("description")).strip():
            st.caption(row["description"])


def render_rule_tab(ctx: HomePageContext):
    if ctx.active_rule_df.empty:
        render_empty_state("Nenhuma regra cadastrada.")
        return
    row = ctx.active_rule_df.iloc[0]
    st.markdown(f"### {row['title']}")
    st.caption(f"Versão: {row.get('version', '-')}, atualizado em {row.get('updated_at', '-')}")
    st.markdown(row["content_md"])


def render_calendar_tab(ctx: HomePageContext):
    if ctx.calendar_df.empty:
        render_empty_state("Nenhum evento cadastrado.")
        return
    st.dataframe(ctx.calendar_df, use_container_width=True, hide_index=True)


def render_draft_tab(ctx: HomePageContext):
    if ctx.draft_df.empty:
        render_empty_state("Nenhuma pick cadastrada.")
        return
    show_df = ctx.draft_df[[
        "season", "round", "pick_number", "original_team_name", "current_team_name",
        "selected_player", "status", "notes",
    ]].rename(columns={
        "season": "Temporada",
        "round": "Round",
        "pick_number": "Pick",
        "original_team_name": "Time original",
        "current_team_name": "Time atual",
        "selected_player": "Jogador selecionado",
        "status": "Status",
        "notes": "Observações",
    })
    st.dataframe(show_df, use_container_width=True, hide_index=True)


def _get_next_event_title(calendar_df):
    if calendar_df is None or calendar_df.empty or "start_date" not in calendar_df.columns:
        return "-"
    df = calendar_df.copy()
    df["start_date"] = pd.to_datetime(df["start_date"], errors="coerce").dt.date
    today = date.today()
    future = df[df["start_date"].notna() & (df["start_date"] >= today)].sort_values("start_date")
    if future.empty:
        return "-"
    return str(future.iloc[0].get("title", "-"))


def render_home_overview(ctx: HomePageContext):
    st.markdown("## Visão geral")
    c1, c2, c3, c4 = st.columns(4)

    rule_title = ctx.active_rule_df.iloc[0]["title"] if not ctx.active_rule_df.empty else "-"
    next_event = _get_next_event_title(ctx.calendar_df)
    draft_status = "-"
    if not ctx.draft_df.empty and "status" in ctx.draft_df.columns:
        draft_status = str(ctx.draft_df.iloc[0].get("status", "-"))
    recent_activity = sum(len(df) for df in ctx.posts_by_tab.values()) + sum(len(df) for df in ctx.comments_by_tab.values())

    c1.metric("Regra vigente", rule_title)
    c2.metric("Próximo evento", next_event)
    c3.metric("Draft", draft_status)
    c4.metric("Atividades", recent_activity)


def render_feed_tab(tab_key: str, ctx: HomePageContext):
    st.markdown("## Feed da aba")
    render_posts(tab_key, ctx)
    render_comments(tab_key, ctx)


def render_home_tabs(ctx: HomePageContext):
    render_home_overview(ctx)
    st.divider()

    tab_labels = ctx.tabs_df["tab_label"].tolist() if "tab_label" in ctx.tabs_df.columns else []
    tab_keys = ctx.tabs_df["tab_key"].tolist() if "tab_key" in ctx.tabs_df.columns else []
    tab_containers = st.tabs(tab_labels)

    for idx, tab in enumerate(tab_containers):
        tab_key = tab_keys[idx]
        tab_label = tab_labels[idx]

        with tab:
            st.subheader(tab_label)

            if tab_key == "regras":
                render_rule_tab(ctx)
            elif tab_key == "calendario":
                render_calendar_tab(ctx)
            elif tab_key == "draft":
                render_draft_tab(ctx)
            elif tab_key == "jogos":
                render_links_section("jogos", ctx)
            elif tab_key == "links":
                render_links_section("links", ctx)
            else:
                st.caption(f"Mural da aba {tab_label}.")

            render_feed_tab(tab_key, ctx)