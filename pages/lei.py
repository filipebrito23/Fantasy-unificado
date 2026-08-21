from __future__ import annotations

from datetime import datetime, timezone

import pandas as pd
import streamlit as st
from sqlalchemy import text

from app_lib.auth_v5 import authenticate_user_v5, change_password_v5, create_user_v5, get_all_users_v5
from app_lib.auction_formatters import format_remaining, formatar_brl, valor_por_extenso
from app_lib.auction_service import (
    _contract_year_limits,
    close_expired_bids_v5,
    delete_bid_v5,
    get_all_bids_v5,
    get_audit_rows_v5,
    get_bid_history_v5,
    get_players_with_state_v5,
    get_team_rows_v5,
    submit_bid_v5,
    update_bid_v5,
)
from app_lib.db_v5 import engine, healthcheck_db_v5, init_db_v5, is_postgres_v5


POSITIONS = ["Todas", "PG", "PG_SG", "SG", "SG_SF", "SF", "SF_PF", "PF", "PF_C", "C"]
STATUS_FILTERS = ["Todos", "OPEN", "CLOSED"]

st.set_page_config(page_title="Leilão da Free Agency - NBA Keeper", layout="wide")


def get_environment_label_v5():
    app_cfg = st.secrets.get("app", {})
    return str(app_cfg.get("environment", "development")).lower()


def startup_v5():
    if st.session_state.get("startup_done_v5"):
        return True, None
    try:
        healthcheck_db_v5()
        init_db_v5()
        close_expired_bids_v5()
        st.session_state["startup_done_v5"] = True
        return True, None
    except Exception as e:
        return False, str(e)


def is_admin(user):
    return str(user.get("role", "")).lower() == "admin"


def logout_v5():
    st.session_state.user_v5 = None
    st.rerun()


def ensure_session():
    if "user_v5" not in st.session_state:
        st.session_state.user_v5 = None


def filter_players(df: pd.DataFrame, status_filter: str) -> pd.DataFrame:
    if df.empty:
        return df
    if status_filter == "Todos":
        return df
    return df[df["status"].fillna("").astype(str).str.upper() == status_filter.upper()]


def render_login():
    st.title("Leilão NBA Fantasy")
    st.subheader("Login por e-mail")
    with st.form("login_form_v5"):
        email = st.text_input("E-mail")
        password = st.text_input("Senha", type="password")
        submitted = st.form_submit_button("Entrar")
        if submitted:
            user = authenticate_user_v5(email, password)
            if user:
                st.session_state.user_v5 = user
                st.rerun()
            else:
                st.error("E-mail ou senha inválidos.")


def render_password_change(user):
    st.warning("Você precisa trocar sua senha antes de continuar.")
    with st.form("change_password_first_login_v5"):
        new_password = st.text_input("Nova senha", type="password")
        confirm_password = st.text_input("Confirmar nova senha", type="password")
        submit_change = st.form_submit_button("Salvar nova senha")
        if submit_change:
            if not new_password or len(new_password) < 6:
                st.error("A senha deve ter pelo menos 6 caracteres.")
            elif new_password != confirm_password:
                st.error("As senhas não coincidem.")
            else:
                change_password_v5(user["user_id"], new_password)
                st.session_state.user_v5["must_change_password"] = 0
                st.success("Senha alterada com sucesso.")
                st.rerun()


def theme_colors():
    bg = st.get_option("theme.backgroundColor") or "#ffffff"
    dark = str(bg).lower() not in ("#ffffff", "#fff", "white")
    if dark:
        return {
            "dark": True,
            "panel_bg": "#1f1f1f",
            "panel_border": "#3a3a3a",
            "text": "#ffffff",
            "muted": "#cfcfcf",
        }
    return {
        "dark": False,
        "panel_bg": "#ffffff",
        "panel_border": "#dddddd",
        "text": "#111111",
        "muted": "#666666",
    }


def badge_html(text, bg, fg="#ffffff"):
    return f"""
    <span style="
        display:inline-block;
        padding:4px 10px;
        border-radius:999px;
        background:{bg};
        color:{fg};
        font-size:12px;
        font-weight:700;
        line-height:1.2;
        margin-right:6px;
        margin-bottom:6px;
        white-space:nowrap;
    ">{text}</span>
    """


def card_html(title, value, subtitle="", accent="#4f81bd", dark=False):
    bg = "#1f1f1f" if dark else "#ffffff"
    border = "#3a3a3a" if dark else "#dddddd"
    title_color = "#cfcfcf" if dark else "#666666"
    value_color = "#ffffff" if dark else "#111111"
    sub_color = "#b5b5b5" if dark else "#666666"
    return f"""
    <div style="
        border:1px solid {border};
        border-left:6px solid {accent};
        border-radius:14px;
        padding:16px 18px;
        background:{bg};
        box-shadow:0 1px 4px rgba(0,0,0,0.08);
        height:100%;
        color:{value_color};
    ">
        <div style="font-size:13px; color:{title_color}; text-transform:uppercase; letter-spacing:0.4px;">
            {title}
        </div>
        <div style="font-size:26px; font-weight:800; margin-top:6px; color:{value_color};">
            {value}
        </div>
        <div style="font-size:13px; color:{sub_color}; margin-top:6px;">
            {subtitle}
        </div>
    </div>
    """


def urgency_accent(remaining_text: str) -> tuple[str, str]:
    t = str(remaining_text).lower()
    if t in ("encerrado", "expirado", "-", "nan"):
        return "#6c757d", "Sem prazo"
    if "min" in t:
        digits = "".join(ch for ch in t if ch.isdigit())
        try:
            mins = int(digits) if digits else 0
        except Exception:
            mins = 0
        if mins <= 10:
            return "#d62728", "Urgência crítica"
        if mins <= 30:
            return "#ff8c00", "Urgência alta"
        return "#2ca02c", "Urgência moderada"
    if "h" in t:
        return "#ff8c00", "Urgência alta"
    return "#2ca02c", "Sem urgência crítica"


def render_players_tab(position=None, status_filter=None):
    colors = theme_colors()

    st.subheader("Propostas")
    st.caption("Monitore propostas ativas, tempo restante e situação de cada jogador.")

    # Valores padrão
    if position is None:
        position = "Todas"
    if status_filter is None:
        status_filter = "Todos"

    players = pd.DataFrame(get_players_with_state_v5(position))
    players = filter_players(players, status_filter)

    if players.empty:
        st.info("Nenhum jogador encontrado para os filtros atuais.")
        return

    players["tempo_restante"] = players["expires_at"].apply(format_remaining)
    players["tipo"] = players["is_renewal"].apply(lambda x: "Renovação" if x == 1 else "Oferta")
    players["valor_fmt"] = players["proposta_ativa"].apply(lambda x: formatar_brl(float(x)) if pd.notna(x) else "-")

    status_series = players["status"].fillna("").astype(str).str.upper()
    open_players = players[status_series == "OPEN"].copy()
    closed_players = players[status_series == "CLOSED"].copy()

    c1, c2, c3, c4 = st.columns(4)
    with c1:
        st.markdown(card_html("Jogadores exibidos", len(players), "Total no filtro atual", "#4f81bd", dark=colors["dark"]), unsafe_allow_html=True)
    with c2:
        st.markdown(card_html("Propostas abertas", len(open_players), "Em monitoramento", "#2ca02c", dark=colors["dark"]), unsafe_allow_html=True)
    with c3:
        st.markdown(card_html("Propostas encerradas", len(closed_players), "Já finalizadas", "#d62728", dark=colors["dark"]), unsafe_allow_html=True)
    with c4:
        if not open_players.empty:
            soonest = open_players.sort_values("expires_at").iloc[0]
            st.markdown(card_html("Mais urgente", format_remaining(soonest["expires_at"]), soonest["player_name"], "#ff9900", dark=colors["dark"]), unsafe_allow_html=True)
        else:
            st.markdown(card_html("Mais urgente", "-", "Sem propostas abertas", "#999999", dark=colors["dark"]), unsafe_allow_html=True)

    st.markdown("### Destaques")
    if open_players.empty:
        st.info("Nenhuma proposta ativa no momento.")
    else:
        top_players = open_players.sort_values("expires_at").head(3).copy()
        cols_cards = st.columns(min(3, len(top_players)))
        for idx, (_, row) in enumerate(top_players.iterrows()):
            accent, urgency_label = urgency_accent(row["tempo_restante"])
            status_bg = "#2ca02c" if str(row["status"]).upper() == "OPEN" else "#6c757d"
            tipo_bg = "#1f77b4" if row["tipo"] == "Oferta" else "#9467bd"
            card_bg = colors["panel_bg"]
            card_border = colors["panel_border"]
            text_color = colors["text"]
            muted = colors["muted"]
            with cols_cards[idx]:
                st.markdown(
                    f"""
                    <div style="
                        border:1px solid {card_border};
                        border-radius:16px;
                        padding:16px;
                        background:{card_bg};
                        box-shadow:0 2px 8px rgba(0,0,0,0.06);
                        min-height:265px;
                        color:{text_color};
                    ">
                        <div style="font-size:12px; color:{muted}; text-transform:uppercase; letter-spacing:0.4px;">Proposta ativa</div>
                        <div style="font-size:22px; font-weight:800; margin-top:6px; color:{text_color};">{row['player_name']}</div>
                        <div style="margin-top:10px;">{badge_html(str(row['status']), status_bg)}{badge_html(str(row['tipo']), tipo_bg)}{badge_html(urgency_label, accent)}</div>
                        <div style="margin-top:12px; font-size:14px; color:{text_color};"><b>Valor:</b> {row['valor_fmt']}</div>
                        <div style="font-size:14px; color:{text_color};"><b>Tempo restante:</b> {row['tempo_restante']}</div>
                        <div style="font-size:14px; color:{text_color};"><b>Dono:</b> {row['dono'] or '-'}</div>
                        <div style="font-size:14px; color:{text_color};"><b>Time ativo:</b> {row['time_ativo'] or '-'}</div>
                        <div style="margin-top:12px; padding:10px 12px; border-radius:10px; background:{accent}; color:white; font-weight:800; text-align:center;">
                            Proposta ativa: {formatar_brl(float(row['proposta_ativa'])) if pd.notna(row['proposta_ativa']) else '-'}
                        </div>
                    </div>
                    """,
                    unsafe_allow_html=True,
                )

    # Filtros: Posição, Status, Time ativo e Dono (todos abaixo de Destaques)
    filter_row1, filter_row2 = st.columns(2), st.columns(2)

    with filter_row1[0]:
        position = st.selectbox("Posição", POSITIONS, key="auction_position_filter_v1")

    with filter_row1[1]:
        status_filter = st.selectbox("Status", STATUS_FILTERS, key="auction_status_filter_v1")

    with filter_row2[0]:
        active_team_options = ["Todos"]
        if "time_ativo" in players.columns:
            active_team_values = (
                players["time_ativo"]
                .dropna()
                .astype(str)
                .replace("", pd.NA)
                .dropna()
                .unique()
                .tolist()
            )
            active_team_options += sorted(active_team_values)

        selected_active_team = st.selectbox(
            "Time ativo",
            active_team_options,
            key="auction_active_team_filter_v1",
        )

    with filter_row2[1]:
        owner_options = ["Todos"]
        if "dono" in players.columns:
            owner_values = (
                players["dono"]
                .dropna()
                .astype(str)
                .replace("", pd.NA)
                .dropna()
                .unique()
                .tolist()
            )
            owner_options += sorted(owner_values)

        selected_owner = st.selectbox(
            "Dono",
            owner_options,
            key="auction_owner_filter_v1",
        )

    # Aplicar filtros (Posição, Status, Time ativo, Dono)
    players = pd.DataFrame(get_players_with_state_v5(position))
    players = filter_players(players, status_filter)

    if players.empty:
        st.info("Nenhum jogador encontrado para os filtros atuais.")
        return

    filtered_players = players.copy()

    if selected_active_team != "Todos" and "time_ativo" in filtered_players.columns:
        filtered_players = filtered_players[
            filtered_players["time_ativo"].fillna("").astype(str) == selected_active_team
        ]

    if selected_owner != "Todos" and "dono" in filtered_players.columns:
        filtered_players = filtered_players[
            filtered_players["dono"].fillna("").astype(str) == selected_owner
        ]

    if filtered_players.empty:
        st.info("Nenhum jogador encontrado com esses filtros.")
        return

    players = filtered_players

    players["tempo_restante"] = players["expires_at"].apply(format_remaining)
    players["tipo"] = players["is_renewal"].apply(lambda x: "Renovação" if x == 1 else "Oferta")
    players["valor_fmt"] = players["proposta_ativa"].apply(lambda x: formatar_brl(float(x)) if pd.notna(x) else "-")

    st.markdown("### Lista de propostas")
    cols = ["player_name", "position", "dono", "time_ativo", "valor_fmt", "anos", "tempo_restante", "tipo", "status"]
    st.dataframe(players[cols], use_container_width=True, hide_index=True)

    st.markdown("### Histórico do jogador")
    selected_player = st.selectbox(
        "Ver histórico do jogador",
        players["player_id"].tolist(),
        format_func=lambda pid: players.loc[players["player_id"] == pid, "player_name"].iloc[0],
    )

    history = pd.DataFrame(get_bid_history_v5(selected_player))
    if history.empty:
        st.info("Nenhuma proposta para este jogador ainda.")
    else:
        history["tipo"] = history["is_renewal"].apply(lambda x: "Renovação" if x == 1 else "Oferta")
        history["ativa"] = history["is_active"].apply(lambda x: "Sim" if x == 1 else "Não")
        cols_h = ["bid_id", "team_name", "amount", "years", "created_at", "updated_at", "deleted_at", "delete_reason", "tipo", "ativa", "created_by"]
        st.dataframe(history[cols_h], use_container_width=True, hide_index=True)

def render_bid_form_tab(user):
    colors = theme_colors()

    st.subheader("Nova proposta")
    st.caption("Envie uma nova oferta ou renovação para um jogador aberto.")

    players = pd.DataFrame(get_players_with_state_v5("Todas"))
    open_players = players[players["status"] == "OPEN"] if not players.empty else pd.DataFrame()

    if open_players.empty:
        st.warning("Não há jogadores abertos para lance.")
        return

    with engine.begin() as conn:
        teams = conn.execute(text("SELECT team_id, team_name FROM teams ORDER BY team_name")).fetchall()
        team_map = {name: tid for tid, name in teams}

    player_id = st.selectbox(
        "Jogador",
        open_players["player_id"].tolist(),
        format_func=lambda pid: open_players.loc[open_players["player_id"] == pid, "player_name"].iloc[0],
    )
    selected_row = open_players.loc[open_players["player_id"] == player_id].iloc[0]

    tempo_txt = format_remaining(selected_row["expires_at"])
    accent, urgency_label = urgency_accent(tempo_txt)

    c1, c2, c3, c4 = st.columns(4)
    with c1:
        st.markdown(card_html("Jogador", selected_row["player_name"], "Selecionado para lance", "#4f81bd", dark=colors["dark"]), unsafe_allow_html=True)
    with c2:
        st.markdown(card_html("Proposta ativa", formatar_brl(float(selected_row["proposta_ativa"])) if pd.notna(selected_row["proposta_ativa"]) else "-", "Maior lance atual", accent, dark=colors["dark"]), unsafe_allow_html=True)
    with c3:
        st.markdown(card_html("Tempo restante", tempo_txt, urgency_label, accent, dark=colors["dark"]), unsafe_allow_html=True)
    with c4:
        st.markdown(card_html("Status", str(selected_row["status"]), "Situação atual do leilão", "#2ca02c" if str(selected_row["status"]).upper() == "OPEN" else "#6c757d", dark=colors["dark"]), unsafe_allow_html=True)

    st.markdown(
        f"""
        <div style="
            border:1px solid {colors['panel_border']};
            border-radius:16px;
            padding:16px;
            background:{colors['panel_bg']};
            color:{colors['text']};
            margin-top:16px;
            margin-bottom:16px;
            box-shadow:0 2px 8px rgba(0,0,0,0.06);
        ">
            <div style="font-size:13px; color:{colors['muted']}; text-transform:uppercase;">Proposta em destaque</div>
            <div style="font-size:28px; font-weight:800; margin-top:4px;">{selected_row['player_name']}</div>
            <div style="margin-top:10px;">{badge_html(str(selected_row['status']), '#2ca02c')} {badge_html('Proposta ativa', accent)} {badge_html('Tipo: ' + ('Renovação' if selected_row['is_renewal'] == 1 else 'Oferta'), '#1f77b4' if selected_row['is_renewal'] != 1 else '#9467bd')}</div>
            <div style="margin-top:12px; font-size:14px;"><b>Posição:</b> {selected_row['position']} | <b>Time atual:</b> {selected_row['dono'] or '-'} | <b>Time ativo:</b> {selected_row['time_ativo'] or '-'}</div>
        </div>
        """,
        unsafe_allow_html=True,
    )

    if is_admin(user):
        team_name = st.selectbox("Time", list(team_map.keys()))
        team_id = team_map[team_name]
    else:
        team_id = user["team_id"]
        st.text_input("Time", value=user.get("team_name", ""), disabled=True)

    # Determinar se é renovação
    owner_team_id = selected_row.get("owner_team_id")
    is_renewal_preview = (
        owner_team_id is not None
        and team_id is not None
        and int(owner_team_id) == int(team_id)
    )

    # Buscar proposta ativa atual do jogador
    player_history = pd.DataFrame(get_bid_history_v5(int(player_id)))
    current_active_amount = None
    current_active_years = None

    if not player_history.empty:
        active_preview = player_history[player_history["is_active"] == 1]
        if not active_preview.empty:
            active_row = active_preview.iloc[0]
            current_active_amount = float(active_row["amount"])
            current_active_years = int(active_row["years"])

    amount = st.number_input(
        "Valor da proposta",
        min_value=1_000_000.0,
        step=100_000.0,
        key="amount_preview_v5",
        format="%.2f",
    )

    # Limites de anos por faixa salarial
    years_limits = _contract_year_limits(amount)

    if years_limits is None:
        min_years = 1
        max_years = 4
    else:
        min_years, max_years = years_limits

    # Regra: renovação cobrindo proposta de mesmo valor → mesmos anos
    if (
        is_renewal_preview
        and current_active_amount is not None
        and abs(amount - current_active_amount) < 0.01
        and current_active_years is not None
    ):
        min_years = current_active_years
        max_years = current_active_years

    years = st.number_input(
        "Anos",
        min_value=min_years,
        max_value=max_years,
        value=min_years,
        step=1,
    )

    c5, c6 = st.columns(2)
    with c5:
        st.info(f"Confirmação: {formatar_brl(amount)}")
    with c6:
        st.info(f"Por extenso: {valor_por_extenso(amount)}")

    if st.button("Enviar proposta"):
        ok, msg = submit_bid_v5(
            player_id,
            team_id,
            amount,
            years,
            user["email"],
            user["user_id"],
            user["role"],
            user.get("team_id"),
        )
        if ok:
            st.success(msg)
            st.rerun()
        else:
            st.error(msg)

def render_cap_tab():
    st.subheader("Cap")
    cap_df = pd.DataFrame(get_team_rows_v5())
    if cap_df.empty:
        st.info("Nenhum time carregado.")
        return
    show = cap_df[["team_name", "cap_limit", "used_cap", "available_cap"]].copy()
    show = show.rename(columns={"team_name": "Time", "cap_limit": "Cap", "used_cap": "Usado", "available_cap": "Disponível"})
    st.metric("Times", len(show))
    st.dataframe(show.sort_values("Disponível", ascending=False), use_container_width=True, hide_index=True)


def render_admin_tab(user):
    if user["role"] != "admin":
        st.warning("Acesso restrito ao administrador.")
        return

    st.subheader("Admin")
    tabs = st.tabs(["Propostas", "Usuários", "Auditoria"])

    with tabs[0]:
        bids_df = pd.DataFrame(get_all_bids_v5(300))
        if bids_df.empty:
            st.info("Nenhuma proposta cadastrada.")
        else:
            st.dataframe(bids_df, use_container_width=True, hide_index=True)

        if not bids_df.empty:
            bid_options = bids_df["bid_id"].tolist()
            selected_bid_id = st.selectbox(
                "Selecionar proposta",
                bid_options,
                format_func=lambda bid_id: f"#{bid_id} - {bids_df.loc[bids_df['bid_id']==bid_id, 'player_name'].iloc[0]} / {bids_df.loc[bids_df['bid_id']==bid_id, 'team_name'].iloc[0]}",
            )
            selected_bid = bids_df.loc[bids_df["bid_id"] == selected_bid_id].iloc[0]

            with st.form("admin_edit_bid_form"):
                new_amount = st.number_input("Novo valor", value=float(selected_bid["amount"]), min_value=1000000.0, step=100000.0, format="%.2f")
                new_years = st.number_input("Novos anos", value=int(selected_bid["years"]), min_value=1, max_value=4, step=1)
                edit_submit = st.form_submit_button("Salvar edição")
                if edit_submit:
                    ok, msg = update_bid_v5(selected_bid_id, new_amount, new_years, user["email"], user["user_id"])
                    if ok:
                        st.success(msg)
                        st.rerun()
                    else:
                        st.error(msg)

            with st.form("admin_delete_bid_form"):
                delete_reason = st.text_input("Motivo da exclusão")
                delete_submit = st.form_submit_button("Excluir proposta")
                if delete_submit:
                    ok, msg = delete_bid_v5(selected_bid_id, user["email"], user["user_id"], delete_reason)
                    if ok:
                        st.success(msg)
                        st.rerun()
                    else:
                        st.error(msg)

    with tabs[1]:
        users_df = pd.DataFrame(get_all_users_v5())
        if users_df.empty:
            st.info("Nenhum usuário cadastrado.")
        else:
            st.dataframe(users_df, use_container_width=True, hide_index=True)

        with engine.begin() as conn:
            teams = conn.execute(text("SELECT team_id, team_name FROM teams ORDER BY team_name")).fetchall()
            team_map = {name: tid for tid, name in teams}

        with st.form("create_user_form_v5"):
            new_email = st.text_input("E-mail do usuário")
            new_password = st.text_input("Senha inicial", type="password")
            new_role = st.selectbox("Perfil", ["admin", "team"])
            team_name_new = st.selectbox("Time do usuário", ["-"] + list(team_map.keys()))
            create_submit = st.form_submit_button("Criar usuário")
            if create_submit:
                if not new_email or not new_password:
                    st.error("Preencha e-mail e senha.")
                else:
                    try:
                        team_id_new = team_map.get(team_name_new) if team_name_new != "-" else None
                        create_user_v5(new_email, new_password, new_role, team_id_new, must_change_password=1)
                        st.success("Usuário criado.")
                        st.rerun()
                    except Exception as e:
                        st.error(f"Erro ao criar usuário: {e}")

    with tabs[2]:
        audit_df = pd.DataFrame(get_audit_rows_v5())
        if audit_df.empty:
            st.info("Nenhum evento de auditoria.")
        else:
            st.dataframe(audit_df, use_container_width=True, hide_index=True)


def render_profile_tab(user):
    st.subheader("Perfil")
    with st.form("change_password_profile_v5"):
        new_password = st.text_input("Nova senha", type="password", key="profile_new_password_v5")
        confirm_password = st.text_input("Confirmar nova senha", type="password", key="profile_confirm_password_v5")
        submit_password = st.form_submit_button("Atualizar senha")
        if submit_password:
            if not new_password or len(new_password) < 6:
                st.error("A senha deve ter pelo menos 6 caracteres.")
            elif new_password != confirm_password:
                st.error("As senhas não coincidem.")
            else:
                try:
                    change_password_v5(user["user_id"], new_password)
                    st.success("Senha atualizada com sucesso.")
                except Exception as e:
                    st.error(f"Erro ao atualizar senha: {e}")


def main():
    ensure_session()
    ok_startup, startup_error = startup_v5()
    if not ok_startup:
        st.error(f"Erro ao inicializar aplicação: {startup_error}")
        st.stop()

    st.sidebar.caption(f"Ambiente: {get_environment_label_v5()}")
    st.sidebar.caption(f"Banco: PostgreSQL" if is_postgres_v5() else "SQLite")

    if not st.session_state.user_v5:
        render_login()
        st.stop()

    user = st.session_state.user_v5
    st.sidebar.success(f"Logado como {user['email']} ({user['role']})")
    if user.get("team_name"):
        st.sidebar.write(f"Time vinculado: {user['team_name']}")
    if st.sidebar.button("Sair"):
        logout_v5()

    if user.get("must_change_password") == 1:
        render_password_change(user)
        st.stop()

    st.title("Leilão NBA Fantasy v5")
    main_tab, bid_tab, cap_tab, admin_tab, profile_tab = st.tabs(["Propostas", "Nova proposta", "Cap", "Admin", "Perfil"])

    with main_tab:
        render_players_tab()

    with bid_tab:
        render_bid_form_tab(user)

    with cap_tab:
        render_cap_tab()

    with admin_tab:
        render_admin_tab(user)

    with profile_tab:
        render_profile_tab(user)


if __name__ == "__main__":
    main()