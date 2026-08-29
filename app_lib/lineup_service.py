from __future__ import annotations

from pathlib import Path
from typing import Any, Dict, List, Optional, Set, Tuple

import pandas as pd
from sqlalchemy import text

from app_lib.db_v5 import engine

# -----------------------------------------------------------------------------
# Constantes
# -----------------------------------------------------------------------------

ROSTER_FILE = Path(__file__).parent.parent / "roster.xlsx"

SLOTS_TITULAR = ["PG", "SG", "SF", "PF", "C", "6TH"]
SLOTS_RESERVA = ["PG_RES", "SG_RES", "SF_RES", "PF_RES", "C_RES", "6TH_RES"]
ALL_SLOTS = SLOTS_TITULAR + SLOTS_RESERVA

# Mapeamento de posições compostas da planilha para formato canônico
POSITION_CANONICAL_MAP = {
    "PG": "PG",
    "PGSG": "PG/SG",
    "SG": "SG",
    "SGSF": "SG/SF",
    "SF": "SF",
    "SFPF": "SF/PF",
    "PF": "PF",
    "PFC": "PF/C",
    "C": "C",
}

# Para cada posição canônica, quais slots ela pode ocupar
POSITION_TO_SLOTS_MAP = {
    "PG": {"PG", "6TH"},
    "PG/SG": {"PG", "SG", "6TH"},
    "SG": {"SG", "6TH"},
    "SG/SF": {"SG", "SF", "6TH"},
    "SF": {"SF", "6TH"},
    "SF/PF": {"SF", "PF", "6TH"},
    "PF": {"PF", "6TH"},
    "PF/C": {"PF", "C", "6TH"},
    "C": {"C", "6TH"},
}


# -----------------------------------------------------------------------------
# Helpers de posição
# -----------------------------------------------------------------------------


def normalize_position(raw_pos: str) -> str:
    """
    Normaliza a posição vinda da planilha (ex: 'PGSG' -> 'PG/SG').
    Se não encontrar, retorna a própria string upper.
    """
    p = str(raw_pos).upper().strip()
    return POSITION_CANONICAL_MAP.get(p, p)


def slots_allowed_for_position(position: str) -> Set[str]:
    """
    Dada uma posição canônica (ex: 'PG/SG'), retorna o conjunto de slots
    que esse jogador pode ocupar (ex: {'PG', 'SG', '6TH'}).
    """
    return POSITION_TO_SLOTS_MAP.get(position, {"6TH"})


# -----------------------------------------------------------------------------
# Carregamento de dados (roster e players)
# -----------------------------------------------------------------------------


def load_roster_main(team_id: int) -> pd.DataFrame:
    """
    Carrega o elenco principal (main) de um time a partir do roster.xlsx.
    Retorna DataFrame com colunas: player_id, Jogador (nome), etc.
    """
    if not ROSTER_FILE.exists():
        raise FileNotFoundError(f"Arquivo {ROSTER_FILE} não encontrado.")

    df_roster = pd.read_excel(ROSTER_FILE, sheet_name="roster")

    # Filtra apenas roster principal do time
    df_main = df_roster[
        (df_roster["team_id"] == team_id)
    ].copy()

    if df_main.empty:
        return df_main

    # Garante player_id como int
    if "player_id" in df_main.columns:
        df_main["player_id"] = pd.to_numeric(df_main["player_id"], errors="coerce").fillna(0).astype(int)

    return df_main


def load_players_df() -> pd.DataFrame:
    """
    Carrega a aba 'players' do roster_vf.xlsx.
    Retorna DataFrame com colunas: player_id, position, etc.
    """
    if not ROSTER_FILE.exists():
        raise FileNotFoundError(f"Arquivo {ROSTER_FILE} não encontrado.")

    df_players = pd.read_excel(ROSTER_FILE, sheet_name="players")

    if "player_id" in df_players.columns:
        df_players["player_id"] = pd.to_numeric(df_players["player_id"], errors="coerce").fillna(0).astype(int)

    return df_players


def build_elenco_principal_dict(team_id: int) -> Dict[int, Dict[str, Any]]:
    """
    Retorna um dicionário {player_id: info_do_jogador} para o elenco principal do time.
    info_do_jogador inclui:
      - player_id
      - nome
      - position_canonical
      - allowed_slots
    """
    df_main = load_roster_main(team_id)
    df_players = load_players_df()

    if df_main.empty:
        return {}

    # Merge com players para pegar posição
    if "player_id" in df_players.columns and "player_id" in df_main.columns:
        df_merged = pd.merge(
            df_main,
            df_players[["player_id", "position"]],
            on="player_id",
            how="left",
            suffixes=("_roster", "_players"),
        )
    else:
        df_merged = df_main.copy()
        if "position" not in df_merged.columns:
            df_merged["position"] = ""

    elenco_dict: Dict[int, Dict[str, Any]] = {}

    for _, row in df_merged.iterrows():
        pid = int(row["player_id"])
        nome = row.get("Jogador") or row.get("playername") or f"Jogador {pid}"
        raw_pos = str(row.get("position", "")).upper().strip()
        pos_canonical = normalize_position(raw_pos)
        allowed = slots_allowed_for_position(pos_canonical)

        elenco_dict[pid] = {
            "player_id": pid,
            "nome": nome,
            "position_raw": raw_pos,
            "position_canonical": pos_canonical,
            "allowed_slots": allowed,
        }

    return elenco_dict


# -----------------------------------------------------------------------------
# Validação de escalação
# -----------------------------------------------------------------------------


def validate_lineup(
    team_id: int,
    lineup_dict: Dict[str, Optional[int]],
) -> Tuple[bool, List[str]]:
    """
    Valida uma escalação completa (12 slots).

    lineup_dict: {slot: player_id ou None}
      - slot em ALL_SLOTS
      - player_id = int ou None

    Retorna (ok, errors), onde:
      - ok = True se não houver erros
      - errors = lista de mensagens de erro
    """
    errors: List[str] = []

    # 1) Verifica se todos os slots estão preenchidos
    for slot in ALL_SLOTS:
        if lineup_dict.get(slot) is None:
            errors.append(f"Slot {slot} não preenchido.")

    if errors:
        return False, errors

    player_ids = [pid for pid in lineup_dict.values() if pid is not None]

    # 2) Carrega elenco principal do time
    elenco = build_elenco_principal_dict(team_id)

    if not elenco:
        errors.append(f"Time {team_id} não possui elenco principal carregado.")
        return False, errors

    # 3) Verifica se todos os jogadores estão no elenco principal
    for slot, pid in lineup_dict.items():
        if pid not in elenco:
            errors.append(f"Jogador {pid} no slot {slot} não está no elenco principal do time.")

    if errors:
        return False, errors

    # 4) Verifica repetição de jogadores (máx 2 vezes)
    from collections import Counter

    counts = Counter(player_ids)
    for pid, cnt in counts.items():
        if cnt > 2:
            nome = elenco[pid]["nome"]
            errors.append(f"Jogador {nome} (id={pid}) aparece {cnt} vezes na escalação (máx 2).")

    if errors:
        return False, errors

    # 5) Verifica titulares distintos
    titulares = [lineup_dict[slot] for slot in SLOTS_TITULAR if lineup_dict.get(slot) is not None]
    if len(titulares) != len(set(titulares)):
        errors.append("Há jogadores repetidos no time titular.")

    if errors:
        return False, errors

    # 6) Verifica: titular e reserva da mesma posição
    # Ex: PG e PG_RES não podem ser o mesmo jogador
    for base in ["PG", "SG", "SF", "PF", "C", "6TH"]:
        slot_tit = base
        slot_res = f"{base}_RES"
        if lineup_dict.get(slot_tit) == lineup_dict.get(slot_res):
            pid = lineup_dict[slot_tit]
            nome = elenco[pid]["nome"]
            errors.append(f"Jogador {nome} não pode ser titular e reserva em {base}.")

    if errors:
        return False, errors

    # 7) Verifica compatibilidade de posição x slot.
    # Slots de reserva usam o mesmo critério de posição do titular:
    # PG_RES -> PG, SG_RES -> SG, ... e 6TH_RES -> 6TH.
    for slot, pid in lineup_dict.items():
        info = elenco[pid]
        allowed = info["allowed_slots"]

        base_slot = slot.replace("_RES", "")

        if base_slot not in allowed:
            nome = info["nome"]
            pos = info["position_canonical"]
            errors.append(
                f"Jogador {nome} (posição {pos}) não pode ocupar o slot {slot}."
            )

    if errors:
        return False, errors

    return True, []


# -----------------------------------------------------------------------------
# Persistência (ler/salvar escalação)
# -----------------------------------------------------------------------------


def save_lineup(
    team_id: int,
    lineup_dict: Dict[str, int],
    user_id: int,
) -> Tuple[bool, List[str]]:
    """
    Salva (ou substitui) a escalação de um time.

    lineup_dict: {slot: player_id} para todos os 12 slots.

    Retorna (ok, errors).
    """
    # Valida primeiro
    ok, errors = validate_lineup(team_id, lineup_dict)  # type: ignore[arg-type]
    if not ok:
        return False, errors

    with engine.begin() as conn:
        # Verifica se já existe escalação para esse time
        existing = conn.execute(
            text("SELECT lineup_id FROM lineups WHERE team_id = :team_id"),
            {"team_id": team_id},
        ).scalar()

        if existing is None:
            # Cria nova escalação
            lineup_id = conn.execute(
                text(
                    """
                    INSERT INTO lineups (team_id, updated_at, updated_by)
                    VALUES (:team_id, NOW(), :updated_by)
                    RETURNING lineup_id
                    """
                ),
                {"team_id": team_id, "updated_by": user_id},
            ).scalar()
        else:
            lineup_id = int(existing)
            # Atualiza timestamp e usuário
            conn.execute(
                text(
                    """
                    UPDATE lineups
                    SET updated_at = NOW(),
                        updated_by = :updated_by
                    WHERE lineup_id = :lineup_id
                    """
                ),
                {"updated_by": user_id, "lineup_id": lineup_id},
            )

            # Remove slots antigos
            conn.execute(
                text("DELETE FROM lineup_slots WHERE lineup_id = :lineup_id"),
                {"lineup_id": lineup_id},
            )

        # Insere os 12 slots
        for slot, player_id in lineup_dict.items():
            conn.execute(
                text(
                    """
                    INSERT INTO lineup_slots (lineup_id, slot, player_id)
                    VALUES (:lineup_id, :slot, :player_id)
                    """
                ),
                {
                    "lineup_id": lineup_id,
                    "slot": slot,
                    "player_id": player_id,
                },
            )

    return True, []


def load_lineup(team_id: int) -> Optional[Dict[str, Optional[int]]]:
    """
    Carrega a escalação de um time.
    Retorna dicionário {slot: player_id ou None} ou None se não existir.
    """
    with engine.begin() as conn:
        lineup_id = conn.execute(
            text("SELECT lineup_id FROM lineups WHERE team_id = :team_id"),
            {"team_id": team_id},
        ).scalar()

        if lineup_id is None:
            return None

        rows = conn.execute(
            text(
                """
                SELECT slot, player_id
                FROM lineup_slots
                WHERE lineup_id = :lineup_id
                """
            ),
            {"lineup_id": lineup_id},
        ).fetchall()

        result: Dict[str, Optional[int]] = {slot: None for slot in ALL_SLOTS}
        for slot, player_id in rows:
            result[slot] = player_id

        return result


def load_all_lineups() -> Dict[int, Dict[str, Optional[int]]]:
    """
    Carrega todas as escalações de todos os times.
    Retorna {team_id: {slot: player_id ou None}}.
    """
    with engine.begin() as conn:
        rows = conn.execute(
            text(
                """
                SELECT l.team_id, ls.slot, ls.player_id
                FROM lineups l
                JOIN lineup_slots ls ON ls.lineup_id = l.lineup_id
                ORDER BY l.team_id, ls.slot
                """
            )
        ).fetchall()

    lineups_by_team: Dict[int, Dict[str, Optional[int]]] = {}

    for team_id, slot, player_id in rows:
        if team_id not in lineups_by_team:
            lineups_by_team[team_id] = {s: None for s in ALL_SLOTS}
        lineups_by_team[team_id][slot] = player_id

    return lineups_by_team


def get_lineup_metadata(team_id: int) -> Optional[Dict[str, Any]]:
    """
    Retorna metadados da escalação de um time (updated_at, updated_by).
    """
    with engine.begin() as conn:
        row = conn.execute(
            text(
                """
                SELECT l.updated_at, l.updated_by, u.email
                FROM lineups l
                LEFT JOIN users u ON u.user_id = l.updated_by
                WHERE l.team_id = :team_id
                """
            ),
            {"team_id": team_id},
        ).fetchone()

        if row is None:
            return None

        return {
            "updated_at": row.updated_at,
            "updated_by": row.updated_by,
            "updated_by_email": row.email,
        }