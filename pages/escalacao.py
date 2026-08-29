from __future__ import annotations

from typing import Any, Dict, List, Optional
from sqlalchemy import text
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

@st.cache_data(show_spinner=False)
def get_elenco_cached(team_id: int) -> Dict[int, Dict[str, Any]]:
    """
    Carrega o elenco principal uma vez por time e mantém em cache.
    Evita reler roster.xlsx e a aba players a cada selectbox.
    """
    return build_elenco_principal_dict(team_id)

def render_lineup_form(team_id: int, user: Dict[str, Any]):
    """
    Renderiza a escalação dentro de um único formulário.

    Benefícios:
    - Não há refresh a cada jogador selecionado.
    - As opções são filtradas somente pela posição compatível.
    - Regras de repetição são avaliadas apenas quando o usuário salva.
    - Limpar e Carregar recriam os widgets com valores corretos.
    """
    if not can_edit_team(team_id, user):
        st.warning("Você não tem permissão para editar este time.")
        return

    metadata = get_lineup_metadata(team_id)
    elenco = get_elenco_cached(team_id)

    if not elenco:
        st.warning("Este time não possui jogadores no elenco principal.")
        return

    st.subheader("Escalação")

    if metadata:
        updated_at = metadata.get("updated_at")
        updated_by_email = metadata.get("updated_by_email")
        st.caption(
            f"Última atualização: {updated_at} por "
            f"{updated_by_email or 'desconhecido'}"
        )
    else:
        st.caption("Nenhuma escalação salva ainda.")

    # Estado de trabalho: a escalação que será exibida/alterada no formulário.
    if "escalacao_lineup_state" not in st.session_state:
        st.session_state.escalacao_lineup_state = {}

    # Essa versão muda nos comandos Limpar e Carregar.
    # Com isso, os widgets ganham novas keys e são reconstruídos de verdade.
    if "escalacao_form_version" not in st.session_state:
        st.session_state.escalacao_form_version = 0

    last_team = st.session_state.get("escalacao_last_team_id")

    # Ao trocar de time, carrega a escalação daquele time ou inicia vazia.
    if last_team != team_id:
        loaded_lineup = load_lineup(team_id) or {
            slot: None for slot in ALL_SLOTS
        }

        st.session_state.escalacao_last_team_id = team_id
        st.session_state.escalacao_lineup_state = dict(loaded_lineup)
        st.session_state.escalacao_form_version += 1

    # Garante os 12 slots no estado.
    for slot in ALL_SLOTS:
        if slot not in st.session_state.escalacao_lineup_state:
            st.session_state.escalacao_lineup_state[slot] = None

    # Mapa pronto para os 12 selects. Cada posição usa apenas o slot-base:
    # PG_RES usa PG; 6TH_RES usa 6TH.
    options_by_slot: Dict[str, List[int]] = {}
    label_by_player: Dict[int, str] = {}

    for pid, info in elenco.items():
        label_by_player[int(pid)] = (
            f"{info['nome']} ({info['position_canonical']})"
        )

    for slot in ALL_SLOTS:
        base_slot = slot.replace("_RES", "")

        eligible_ids = [
            int(pid)
            for pid, info in elenco.items()
            if base_slot in info.get("allowed_slots", set())
        ]

        eligible_ids.sort(
            key=lambda pid: label_by_player[pid].casefold()
        )

        # None é a primeira opção para que nenhum jogador seja pré-selecionado.
        options_by_slot[slot] = [None] + eligible_ids

    # A versão faz Limpar e Carregar funcionarem de forma consistente.
    version = st.session_state.escalacao_form_version

    # Os comandos ficam fora do form porque atualizam os valores exibidos.
    action_col1, action_col2, action_col3 = st.columns([2, 1, 1])

    with action_col2:
        clear_clicked = st.button(
            "Limpar",
            key=f"escalacao_clear_{team_id}",
        )

    with action_col3:
        load_clicked = st.button(
            "Carregar escalação atual",
            key=f"escalacao_load_{team_id}",
        )

    if clear_clicked:
        st.session_state.escalacao_lineup_state = {
            slot: None for slot in ALL_SLOTS
        }
        st.session_state.escalacao_form_version += 1
        st.rerun()

    if load_clicked:
        saved_lineup = load_lineup(team_id)

        if saved_lineup:
            st.session_state.escalacao_lineup_state = {
                slot: saved_lineup.get(slot)
                for slot in ALL_SLOTS
            }
            st.session_state.escalacao_form_version += 1
            st.rerun()
        else:
            st.info("Nenhuma escalação salva para este time.")

    # Form único: nenhuma escolha individual faz refresh.
    with st.form(
        key=f"escalacao_form_{team_id}_{version}",
        clear_on_submit=False,
    ):
        st.markdown("### Titulares")

        titular_cols = st.columns(3)
        selected_lineup: Dict[str, Optional[int]] = {}

        for index, slot in enumerate(SLOTS_TITULAR):
            with titular_cols[index % 3]:
                title = "6th" if slot == "6TH" else slot

                current_value = st.session_state.escalacao_lineup_state.get(slot)
                slot_options = options_by_slot[slot]

                if current_value not in slot_options:
                    current_value = None

                selected_lineup[slot] = st.selectbox(
                    title,
                    options=slot_options,
                    index=slot_options.index(current_value),
                    format_func=lambda pid: (
                        "Selecione um jogador"
                        if pid is None
                        else label_by_player[pid]
                    ),
                    key=f"escalacao_widget_{team_id}_{version}_{slot}",
                )

        st.markdown("### Reservas")

        reserva_cols = st.columns(3)

        for index, slot in enumerate(SLOTS_RESERVA):
            with reserva_cols[index % 3]:
                base_slot = slot.replace("_RES", "")
                title = "6th Reserva" if base_slot == "6TH" else f"{base_slot} Reserva"

                current_value = st.session_state.escalacao_lineup_state.get(slot)
                slot_options = options_by_slot[slot]

                if current_value not in slot_options:
                    current_value = None

                selected_lineup[slot] = st.selectbox(
                    title,
                    options=slot_options,
                    index=slot_options.index(current_value),
                    format_func=lambda pid: (
                        "Selecione um jogador"
                        if pid is None
                        else label_by_player[pid]
                    ),
                    key=f"escalacao_widget_{team_id}_{version}_{slot}",
                )

        st.divider()

        save_clicked = st.form_submit_button(
            "Salvar escalação",
            type="primary",
            use_container_width=True,
        )

    # Só depois do submit o Streamlit processa a escalação inteira.
    if not save_clicked:
        return

    st.session_state.escalacao_lineup_state = dict(selected_lineup)

    missing_slots = [
        slot
        for slot in ALL_SLOTS
        if selected_lineup.get(slot) is None
    ]

    if missing_slots:
        labels = {
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

        missing_labels = [
            labels.get(slot, slot)
            for slot in missing_slots
        ]

        st.error(
            "Preencha todos os slots antes de salvar: "
            + ", ".join(missing_labels)
        )
        return

    lineup_to_save = {
        slot: int(player_id)
        for slot, player_id in selected_lineup.items()
        if player_id is not None
    }

    ok, errors = save_lineup(
        team_id=team_id,
        lineup_dict=lineup_to_save,
        user_id=user["user_id"],
    )

    if not ok:
        st.error("A escalação não pôde ser salva. Corrija os itens abaixo:")
        for error in errors:
            st.error(f"• {error}")
        return

    st.success("Escalação salva com sucesso.")

    # Atualiza o estado com o que foi salvo e recria o form.
    st.session_state.escalacao_lineup_state = dict(lineup_to_save)
    st.session_state.escalacao_form_version += 1
    st.rerun()

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