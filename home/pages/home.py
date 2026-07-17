import pandas as pd
import streamlit as st

from auth_v5 import authenticate_user_v5
from home_service import (
    ensure_default_home_tabs,
    get_home_tabs,
    get_active_rule,
    get_calendar_events,
    get_draft_board,
    get_links_by_section,
    get_posts_by_tab,
    get_comments,
    create_comment,
    create_post,
)


def require_login_v5():
    if "user_v5" not in st.session_state or not st.session_state.user_v5:
        st.warning("Faça login para acessar esta página.")
        st.stop()
    return st.session_state.user_v5


def get_user_display(user):
    if isinstance(user, dict):
        return str(user.get("name") or user.get("username") or user.get("email") or "Usuário")
    return str(user)


def is_admin_user(user):
    if isinstance(user, dict):
        return str(user.get("role", "")).lower() == "admin"
    return False


def render_comments(tab_key: str, user_label: str):
    st.markdown("#### Comentários")
    comments_df = get_comments(tab_key)

    if comments_df.empty:
        st.caption("Sem comentários ainda.")
    else:
        for _, row in comments_df.iterrows():
            pin = "📌 " if bool(row.get("is_pinned")) else ""
            st.markdown(f"**{pin}{row['author']}** — {row['created_at']}")
            st.write(row["comment_text"])
            st.divider()

    comment_text = st.text_area("Novo comentário", key=f"comment_box_{tab_key}")
    if st.button("Publicar comentário", key=f"comment_btn_{tab_key}"):
        if comment_text.strip():
            create_comment(tab_key=tab_key, author=user_label, comment_text=comment_text.strip())
            st.success("Comentário publicado.")
            st.rerun()
        else:
            st.error("Digite um comentário antes de publicar.")


def render_posts(tab_key: str, user, user_label: str):
    posts_df = get_posts_by_tab(tab_key)

    if not posts_df.empty:
        st.markdown("#### Posts")
        for _, row in posts_df.iterrows():
            pin = "📌 " if bool(row.get("is_pinned")) else ""
            st.markdown(f"### {pin}{row['title']}")
            st.caption(f"{row['author']} • {row['created_at']}")
            st.markdown(row["content_md"])
            st.divider()

    if is_admin_user(user):
        with st.expander("Criar post", expanded=False):
            title = st.text_input("Título", key=f"post_title_{tab_key}")
            content_md = st.text_area("Conteúdo", key=f"post_content_{tab_key}", height=180)
            is_pinned = st.checkbox("Fixar post", key=f"post_pinned_{tab_key}")

            if st.button("Publicar post", key=f"post_btn_{tab_key}"):
                if title.strip() and content_md.strip():
                    create_post(
                        tab_key=tab_key,
                        author=user_label,
                        title=title.strip(),
                        content_md=content_md.strip(),
                        is_pinned=is_pinned,
                    )
                    st.success("Post criado.")
                    st.rerun()
                else:
                    st.error("Título e conteúdo são obrigatórios.")


user = require_login_v5()
user_label = get_user_display(user)

ensure_default_home_tabs()
tabs_df = get_home_tabs()

st.title("Home")
st.caption("Página principal da liga")

if tabs_df.empty:
    st.info("Nenhuma aba ativa cadastrada.")
    st.stop()

tab_labels = tabs_df["tab_label"].tolist()
tab_keys = tabs_df["tab_key"].tolist()
tab_containers = st.tabs(tab_labels)

for idx, tab in enumerate(tab_containers):
    tab_key = tab_keys[idx]
    tab_label = tab_labels[idx]

    with tab:
        st.subheader(tab_label)

        if tab_key == "regras":
            rule_df = get_active_rule()
            if rule_df.empty:
                st.info("Nenhuma regra cadastrada.")
            else:
                row = rule_df.iloc[0]
                st.markdown(f"### {row['title']}")
                st.caption(f"Versão: {row.get('version', '-')}, atualizado em {row.get('updated_at', '-')}")
                st.markdown(row["content_md"])

        elif tab_key == "calendario":
            cal_df = get_calendar_events()
            if cal_df.empty:
                st.info("Nenhum evento cadastrado.")
            else:
                st.dataframe(cal_df, use_container_width=True, hide_index=True)

        elif tab_key == "draft":
            draft_df = get_draft_board()
            if draft_df.empty:
                st.info("Nenhuma pick cadastrada.")
            else:
                st.dataframe(draft_df, use_container_width=True, hide_index=True)

        elif tab_key == "jogos":
            links_df = get_links_by_section("jogos")
            if links_df.empty:
                st.info("Nenhum link cadastrado.")
            else:
                for _, row in links_df.iterrows():
                    st.markdown(f"- [{row['label']}]({row['url']})")
                    if pd.notna(row.get("description")) and str(row.get("description")).strip():
                        st.caption(row["description"])

        elif tab_key == "links":
            links_df = get_links_by_section("links")
            if links_df.empty:
                st.info("Nenhum link cadastrado.")
            else:
                for _, row in links_df.iterrows():
                    st.markdown(f"- [{row['label']}]({row['url']})")
                    if pd.notna(row.get("description")) and str(row.get("description")).strip():
                        st.caption(row["description"])

        else:
            st.caption(f"Mural da aba {tab_label}.")

        render_posts(tab_key, user, user_label)
        render_comments(tab_key, user_label)