from __future__ import annotations

from typing import Any, Dict, List, Optional

import pandas as pd
import streamlit as st

from app_lib.db_v5 import engine
from app_lib.lineup_service import (
    ALL_SLOTS,
    SLOTS_TITULAR,
    SLOTS_RESERVA,
    build_elenco_principal_dict,
    load_all_lineups,
    load_lineup,
    save_lineup,
    validate_lineup,
    get_lineup_metadata,
)
from app_lib.role_helpers import is_admin_user
from app_lib.session_helpers import require_login_v5


st.set_page_config(
    page_title="Escalação - NBA Fantasy",
    layout="wide",
)


# -----------------------------------------------------------------------------
# Helpers de sessão e permissão
# -----------------------------------------------------------------------------


def ensure_session():
    if "user_v5" not in st.session_state:
        st.session_state.user_v5 = None


def get_current_user():
    ensure_session()
    return st.session_state.get("user_v5")


def can_edit_team(team_id: int, user: Dict[str, Any]) -> bool:
    """
    Regra de permissão:
    - admin: pode editar qualquer time
    - usuário comum: só pode editar o próprio time (team_id == user['team_id'])
    """
    if is_admin_user(user):
        return True

    user_team_id = user.get("team_id")
    if user_team_id is None:
        return False

    return int(user_team_id) == int(team_id)


# -----------------------------------------------------------------------------
# Helpers de times
# -----------------------------------------------------------------------------


def get_all_teams() -> List[Dict[str, Any]]:
    """
    Retorna lista de times: [{team_id, team_name}, ...]
    """
    from sqlalchemy import text

    with engine.begin() as conn:
        rows = conn.execute(
            text("SELECT team_id, team_name FROM teams ORDER BY team_name")
        ).fetchall()

    return [{"team_id": r.team_id, "team_name": r.team_name} for r in rows]


# -----------------------------------------------------------------------------
# Helpers de jogadores
# -----------------------------------------------------------------------------


def build_player_options(
    team_id: int,
    current_lineup: Optional[Dict[str, Optional[int]]],
    current_slot: str,
) -> List[Dict[str, Any]]:
    """
    Exibe somente jogadores cuja posição seja compatível com o slot.

    Reservas usam slots como PG_RES, SG_RES etc., mas a validação
    de posição deve considerar apenas a posição-base: PG, SG, SF, PF, C ou 6TH.

    Regras de repetição e conflito entre titular/reserva são validadas
    somente ao salvar.
    """
    elenco = build_elenco_principal_dict(team_id)

    if not elenco:
        return []

    # PG_RES -> PG; SG_RES -> SG; 6TH_RES -> 6TH
    base_slot = current_slot.replace("_RES", "")

    options: List[Dict[str, Any]] = []

    for pid, info in elenco.items():
        allowed_slots = info.get("allowed_slots", set())

        if base_slot not in allowed_slots:
            continue

        label = (
            f"{info['nome']} "
            f"({info.get('position_canonical', info.get('position_raw', '-'))})"
        )

        options.append(
            {
                "player_id": int(pid),
                "label": label,
                "disabled": False,
            }
        )

    options.sort(key=lambda item: item["label"].casefold())

    return options


# -----------------------------------------------------------------------------
# UI principal
# -----------------------------------------------------------------------------


def render_team_selector(user: Dict[str, Any]) -> Optional[int]:
    """
    Renderiza seletor de time.
    - admin: vê todos os times
    - usuário comum: vê apenas o próprio time (ou nenhum, se não tiver time)
    """
    teams = get_all_teams()

    if not teams:
        st.error("Nenhum time encontrado.")
        return None

    if is_admin_user(user):
        # Admin pode escolher qualquer time
        team_options = {t["team_name"]: t["team_id"] for t in teams}
    else:
        # Usuário comum: só o próprio time
        user_team_id = user.get("team_id")
        if user_team_id is None:
            st.warning("Você não está vinculado a nenhum time.")
            return None

        user_team = next((t for t in teams if t["team_id"] == user_team_id), None)
        if user_team is None:
            st.warning("Seu time não foi encontrado na base.")
            return None

        team_options = {user_team["team_name"]: user_team["team_id"]}

    if len(team_options) == 1:
        # Se só há uma opção, já seleciona automaticamente
        team_name = list(team_options.keys())[0]
        st.selectbox(
            "Time",
            [team_name],
            index=0,
            disabled=True,
            key="escalacao_team_selector",
        )
        return team_options[team_name]

    team_name = st.selectbox(
        "Time",
        list(team_options.keys()),
        key="escalacao_team_selector",
    )

    return team_options[team_name]


def render_lineup_form(team_id: int, user: Dict[str, Any]):
    """
    Renderiza o formulário de escalação para um time específico.
    """
    if not can_edit_team(team_id, user):
        st.warning("Você não tem permissão para editar este time.")
        return

    # Carrega escalação atual (se existir)
    current_lineup = load_lineup(team_id)
    metadata = get_lineup_metadata(team_id)

    st.subheader("Escalação")

    if metadata:
        updated_at = metadata.get("updated_at")
        updated_by_email = metadata.get("updated_by_email")
        st.caption(
            f"Última atualização: {updated_at} por {updated_by_email or 'desconhecido'}"
        )
    else:
        st.caption("Nenhuma escalação salva ainda.")

    # Inicializa estado da escalação no session_state
    if "escalacao_lineup_state" not in st.session_state:
        st.session_state.escalacao_lineup_state = {}

    # Se mudou de time, reseta o estado
    last_team = st.session_state.get("escalacao_last_team_id")
    if last_team != team_id:
        st.session_state.escalacao_last_team_id = team_id
        st.session_state.escalacao_lineup_state = {}

    # Inicializa slots vazios se necessário
    for slot in ALL_SLOTS:
        if slot not in st.session_state.escalacao_lineup_state:
            st.session_state.escalacao_lineup_state[slot] = (
                current_lineup.get(slot) if current_lineup else None
            )

    # Usa o estado ATUAL (session_state) para calcular opções, não só o current_lineup
    current_lineup_effective = dict(st.session_state.escalacao_lineup_state)

    # Seção de titulares
    st.markdown("### Titulares")
    titular_cols = st.columns(3)

    for idx, slot in enumerate(SLOTS_TITULAR):
        col = titular_cols[idx % 3]
        with col:
            label = slot.replace("6TH", "6th").capitalize()
            options = build_player_options(team_id, current_lineup_effective, slot)

            # Mapeia player_id -> label para o selectbox
            opt_map = {o["player_id"]: o["label"] for o in options if not o["disabled"]}
            current_pid = st.session_state.escalacao_lineup_state.get(slot)

            # Se o valor atual não está nas opções, reseta
            if current_pid is not None and current_pid not in opt_map:
                current_pid = None
                st.session_state.escalacao_lineup_state[slot] = None

            selected = col.selectbox(
                label,
                options=list(opt_map.values()),
                index=(
                    list(opt_map.values()).index(opt_map[current_pid])
                    if current_pid is not None and current_pid in opt_map
                    else 0
                )
                if opt_map
                else 0,
                key=f"escalacao_slot_{slot}",
            )

            # Atualiza estado
            reverse_map = {v: k for k, v in opt_map.items()}
            st.session_state.escalacao_lineup_state[slot] = reverse_map.get(selected)

    # Seção de reservas
    st.markdown("### Reservas")
    reserva_cols = st.columns(3)

    for idx, slot in enumerate(SLOTS_RESERVA):
        col = reserva_cols[idx % 3]
        with col:
            base = slot.replace("_RES", "")
            label = f"{base.replace('6TH', '6th').capitalize()} Reserva"
            options = build_player_options(team_id, current_lineup_effective, slot)

            opt_map = {o["player_id"]: o["label"] for o in options if not o["disabled"]}
            current_pid = st.session_state.escalacao_lineup_state.get(slot)

            if current_pid is not None and current_pid not in opt_map:
                current_pid = None
                st.session_state.escalacao_lineup_state[slot] = None

            selected = col.selectbox(
                label,
                options=list(opt_map.values()),
                index=(
                    list(opt_map.values()).index(opt_map[current_pid])
                    if current_pid is not None and current_pid in opt_map
                    else 0
                )
                if opt_map
                else 0,
                key=f"escalacao_slot_{slot}",
            )

            reverse_map = {v: k for k, v in opt_map.items()}
            st.session_state.escalacao_lineup_state[slot] = reverse_map.get(selected)

    # Botões de ação
    st.divider()

    btn_col1, btn_col2, btn_col3 = st.columns([2, 1, 1])

    with btn_col1:
        if st.button("Salvar escalação", type="primary", key="escalacao_save_btn"):
            lineup_dict = dict(st.session_state.escalacao_lineup_state)

            # Verifica se todos os slots estão preenchidos
            missing = [s for s, v in lineup_dict.items() if v is None]
            if missing:
                st.error(f"Preencha todos os slots. Faltam: {', '.join(missing)}")
            else:
                ok, errors = save_lineup(
                    team_id=team_id,
                    lineup_dict=lineup_dict,  # type: ignore[arg-type]
                    user_id=user["user_id"],
                )
                if ok:
                    st.success("Escalação salva com sucesso!")

                    for slot in ALL_SLOTS:
                        st.session_state.escalacao_lineup_state[slot] = None

                        widget_key = f"escalacao_slot_{slot}"
                        if widget_key in st.session_state:
                            del st.session_state[widget_key]

                    st.rerun()
                else:
                    for err in errors:
                        st.error(err)

    with btn_col2:
        if st.button("Limpar", key="escalacao_clear_btn"):
            for slot in ALL_SLOTS:
                st.session_state.escalacao_lineup_state[slot] = None

                widget_key = f"escalacao_slot_{slot}"
                if widget_key in st.session_state:
                    del st.session_state[widget_key]

            st.rerun()

    with btn_col3:
        if st.button("Carregar escalação atual", key="escalacao_load_btn"):
            current = load_lineup(team_id)

            if current:
                st.session_state.escalacao_lineup_state = dict(current)

                # Remove o estado antigo dos widgets.
                # Assim, os selectboxes serão renderizados novamente
                # usando os valores carregados acima.
                for slot in ALL_SLOTS:
                    widget_key = f"escalacao_slot_{slot}"
                    if widget_key in st.session_state:
                        del st.session_state[widget_key]

                st.success("Escalação atual carregada.")
                st.rerun()
            else:
                st.info("Nenhuma escalação salva para este time.")


def render_export_tab():
    """
    Renderiza aba de exportação das escalações.
    """
    st.subheader("Exportar escalações")

    if st.button("Gerar planilha de escalações"):
        all_lineups = load_all_lineups()
        teams = get_all_teams()

        if not all_lineups:
            st.warning("Nenhuma escalação encontrada.")
            return

        # Monta DataFrame
        # Colunas: Posição, Time1, Time2, ...
        rows = []

        slot_labels = {
            "PG": "PG Titular",
            "SG": "SG Titular",
            "SF": "SF Titular",
            "PF": "PF Titular",
            "C": "C Titular",
            "6TH": "6th Titular",
            "PG_RES": "PG Reserva",
            "SG_RES": "SG Reserva",
            "SF_RES": "SF Reserva",
            "PF_RES": "PF Reserva",
            "C_RES": "C Reserva",
            "6TH_RES": "6th Reserva",
        }

        # Mapa team_id -> team_name
        team_map = {t["team_id"]: t["team_name"] for t in teams}

        # Para cada slot, cria uma linha
        for slot in ALL_SLOTS:
            row = {"Posição": slot_labels.get(slot, slot)}

            for team_id, lineup in all_lineups.items():
                pid = lineup.get(slot)
                team_name = team_map.get(team_id, f"Time {team_id}")

                if pid is None:
                    player_name = ""
                else:
                    # Busca nome do jogador
                    elenco = build_elenco_principal_dict(team_id)
                    player_name = elenco.get(pid, {}).get("nome", f"Jogador {pid}")

                row[team_name] = player_name

            rows.append(row)

        df = pd.DataFrame(rows)

        # Reordena colunas: Posição + times em ordem alfabética
        team_cols = sorted([t["team_name"] for t in teams])
        df = df[["Posição"] + team_cols]

        # Exporta para Excel
        from io import BytesIO

        output = BytesIO()
        with pd.ExcelWriter(output, engine="openpyxl") as writer:
            df.to_excel(writer, index=False, sheet_name="Escalações")

        st.download_button(
            label="Baixar planilha (.xlsx)",
            data=output.getvalue(),
            file_name="escalacoes.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            key="escalacao_export_btn",
        )


def main():
    ensure_session()
    require_login_v5()

    user = get_current_user()
    if not user:
        st.stop()

    st.title("Escalação - NBA Fantasy")

    # Abas: Escalar, Exportar
    tab_escalar, tab_exportar = st.tabs(["Escalar", "Exportar"])

    with tab_escalar:
        team_id = render_team_selector(user)

        if team_id is None:
            st.stop()

        render_lineup_form(team_id, user)

    with tab_exportar:
        render_export_tab()


if __name__ == "__main__":
    main()