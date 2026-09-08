"""
Feature 2b - Importação APENAS de stats dos jogadores.

O script localiza confrontos já existentes em fantasy_games e grava somente
em fantasy_game_stats.

Regra de importação:
- Só grava estatísticas se ambos os times tiverem ao menos algum campo
  estatístico preenchido na planilha.
- Jogadores individuais podem ter estatísticas zeradas.
- Não cria, atualiza ou exclui jogos em fantasy_games.
"""

from __future__ import annotations

import re
import time
import unicodedata
from pathlib import Path

from google.oauth2 import service_account
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError
from sqlalchemy import text

from app_lib.db_v5 import engine


# ============================================================================
# CONFIGURAÇÃO
# ============================================================================

SERVICE_ACCOUNT_FILE = Path(__file__).parent / "service_account.json"
URLS_FILE = Path(__file__).parent / "url-2.txt"

SCOPES = ["https://www.googleapis.com/auth/spreadsheets.readonly"]

COLUMN_MAP = {
    "jogadores": "player_name",
    "pontos": "pts",
    "rebotes": "reb",
    "assistencias": "ast",
    "roubos": "stl",
    "tocos": "blk",
    "bolas de 3": "three_pt",
    "turnovers": "turnovers",
}

STAT_COLUMNS = [
    "pts",
    "reb",
    "ast",
    "stl",
    "blk",
    "three_pt",
    "turnovers",
]

MAX_RETRIES = 3
RETRY_DELAY = 5

# Mapeamento das siglas presentes no título de cada aba para os IDs do Neon.
SIGLA_TO_TEAM_ID = {
    "ABB": 1,   # Alabama Black Bears
    "FRC": 2,   # Franca Celtics
    "GUA": 3,   # Guarulhos Nuggets
    "IRB": 4,   # Itajubá Rabbits
    "KDG": 5,   # Kaipiras da Gema
    "MIB": 6,   # Miami Barons
    "MNT": 7,   # Montreal Turtles
    "NOD": 8,   # New Orleans Dancers
    "OSA": 9,   # Osasco Heat
    "PVK": 10,  # Pelotas Vikings
    "PER": 11,  # Pernambuco Pharynx
    "RBD": 12,  # Recife Black Diamond
    "RBM": 13,  # RJ Black Mamba
    "TCH": 14,  # Tchêltics da Peleia
}


# ============================================================================
# FUNÇÕES AUXILIARES
# ============================================================================

def normalize_text(value: object) -> str:
    """Remove acentos, normaliza espaços e converte o texto para minúsculas."""
    normalized = unicodedata.normalize("NFKD", str(value or ""))
    normalized = "".join(
        char for char in normalized if not unicodedata.combining(char)
    )
    return " ".join(normalized.strip().lower().split())


def extract_spreadsheet_id(url: str) -> str:
    """Extrai o ID da planilha de uma URL do Google Sheets."""
    match = re.search(r"/spreadsheets/d/([a-zA-Z0-9_-]+)", url)

    if match:
        return match.group(1)

    raise ValueError(f"URL inválida: {url}")


def parse_urls_file(filepath: Path) -> list[dict]:
    """Lê o arquivo url-2.txt."""
    urls = []

    with open(filepath, "r", encoding="utf-8") as file:
        for line in file:
            line = line.strip()

            if not line:
                continue

            parts = line.split(" - ", 1)

            if len(parts) != 2:
                print(f"Linha inválida em url-2.txt: {line}")
                continue

            urls.append(
                {
                    "rodada": parts[0].strip(),
                    "url": parts[1].strip(),
                }
            )

    return urls


def get_round_number(rodada: str) -> int:
    """Extrai o número de 'Jogo 1', 'Jogo 2' etc."""
    match = re.search(r"(\d+)", rodada)

    if not match:
        raise ValueError(f"Não foi possível identificar a rodada: {rodada}")

    return int(match.group(1))


def get_team_sigla_from_aba(aba_name: str, team_position: str) -> str:
    """Extrai a sigla da aba no formato 'KDG x TCH'."""
    parts = aba_name.split(" x ")

    if len(parts) == 2:
        return parts[0].strip().upper() if team_position == "A" else parts[1].strip().upper()

    return aba_name.strip().upper()


def get_fantasy_game_id_by_teams(
    round_num: int,
    team_a_id: int,
    team_b_id: int,
    conn,
) -> int | None:
    """
    Busca fantasy_game_id por rodada e time IDs, aceitando qualquer ordem.

    Assim funciona tanto para uma aba 'KDG x TCH' quanto para um jogo
    cadastrado no banco como 'TCH x KDG'.
    """
    result = conn.execute(
        text(
            """
            SELECT fantasy_game_id
            FROM fantasy_games
            WHERE round = :round
              AND (
                    (team_1_id = :team_a_id AND team_2_id = :team_b_id)
                 OR (team_1_id = :team_b_id AND team_2_id = :team_a_id)
              )
            LIMIT 1
            """
        ),
        {
            "round": round_num,
            "team_a_id": team_a_id,
            "team_b_id": team_b_id,
        },
    )

    row = result.fetchone()

    if row:
        return int(row[0])

    return None


def get_player_source_id(player_name: str, conn) -> int | None:
    """Busca source_player_id pelo nome do jogador."""
    result = conn.execute(
        text(
            """
            SELECT source_player_id
            FROM fantasy_players
            WHERE player_name = :player_name
            LIMIT 1
            """
        ),
        {"player_name": player_name.strip()},
    )

    row = result.fetchone()

    return int(row[0]) if row else None


def parse_stat_value(value: object) -> float:
    """
    Converte valores como '15', '53,5', '53.5' e strings vazias para float.
    """
    raw_value = str(value or "").strip()

    if not raw_value:
        return 0.0

    if "," in raw_value and "." in raw_value:
        raw_value = raw_value.replace(".", "").replace(",", ".")
    else:
        raw_value = raw_value.replace(",", ".")

    try:
        return float(raw_value)
    except (TypeError, ValueError):
        return 0.0


def map_header_columns(headers: list) -> dict[str, int]:
    """Mapeia cabeçalhos da planilha para os campos do banco."""
    col_indices: dict[str, int] = {}

    for index, header in enumerate(headers):
        header_clean = normalize_text(header)

        if header_clean in COLUMN_MAP:
            col_indices[COLUMN_MAP[header_clean]] = index

    return col_indices


def has_stat_cell_filled(row: list, col_indices: dict[str, int]) -> bool:
    """
    Verifica se pelo menos uma célula de estatística foi preenchida.

    A checagem é feita pelo conteúdo da célula, antes de converter em número.
    Portanto:
    - célula vazia não conta;
    - '0' conta como preenchido;
    - um atleta zerado é válido;
    - um time inteiro sem nenhum campo preenchido é considerado incompleto.
    """
    for stat_name in STAT_COLUMNS:
        column_index = col_indices.get(stat_name)

        if column_index is None or column_index >= len(row):
            continue

        if str(row[column_index]).strip():
            return True

    return False


def parse_team_data(
    values: list,
    start_row: int,
    col_indices: dict[str, int],
    conn,
    team_id: int,
) -> tuple[list[dict], bool]:
    """
    Faz o parse das seis linhas de jogadores de um time.

    Retorna:
    - lista de jogadores reconhecidos no banco;
    - True/False indicando se havia pelo menos algum preenchimento de stats
      na planilha para aquele time.

    O segundo retorno não depende de o jogador ter sido encontrado no banco.
    """
    players = []
    team_has_filled_stats = False

    name_col = col_indices.get("player_name")

    if name_col is None:
        return players, team_has_filled_stats

    for row_idx in range(start_row, start_row + 6):
        if row_idx >= len(values):
            break

        row = values[row_idx]

        if not row:
            continue

        if name_col >= len(row):
            continue

        player_name = str(row[name_col]).strip()

        if not player_name:
            continue

        if has_stat_cell_filled(row, col_indices):
            team_has_filled_stats = True

        stats = {}

        for stat_name in STAT_COLUMNS:
            col_idx = col_indices.get(stat_name)

            if col_idx is None or col_idx >= len(row):
                stats[stat_name] = 0.0
            else:
                stats[stat_name] = parse_stat_value(row[col_idx])

        source_player_id = get_player_source_id(player_name, conn)

        if source_player_id is None:
            print(f"      Jogador não encontrado: {player_name}")
            continue

        players.append(
            {
                "source_player_id": source_player_id,
                "team_id": team_id,
                "stats": stats,
            }
        )

    return players, team_has_filled_stats


def fetch_with_retry(
    service,
    spreadsheet_id: str,
    range_name: str,
    max_retries: int = MAX_RETRIES,
    retry_delay: int = RETRY_DELAY,
) -> list:
    """Lê dados de uma aba, repetindo em erros temporários da API."""
    for attempt in range(1, max_retries + 1):
        try:
            result = service.spreadsheets().values().get(
                spreadsheetId=spreadsheet_id,
                range=range_name,
            ).execute()

            return result.get("values", [])

        except HttpError as error:
            retryable = error.resp.status in {429, 500, 503}

            if retryable and attempt < max_retries:
                print(
                    f"      Erro {error.resp.status}. "
                    f"Tentativa {attempt}/{max_retries}. "
                    f"Aguardando {retry_delay}s..."
                )
                time.sleep(retry_delay)
                continue

            raise

    return []


def fetch_with_retry_metadata(
    service,
    spreadsheet_id: str,
    max_retries: int = MAX_RETRIES,
    retry_delay: int = RETRY_DELAY,
) -> dict:
    """Lê os metadados da planilha, repetindo em erros temporários."""
    for attempt in range(1, max_retries + 1):
        try:
            return service.spreadsheets().get(
                spreadsheetId=spreadsheet_id
            ).execute()

        except HttpError as error:
            retryable = error.resp.status in {429, 500, 503}

            if retryable and attempt < max_retries:
                print(
                    f"  Erro {error.resp.status}. "
                    f"Tentativa {attempt}/{max_retries}. "
                    f"Aguardando {retry_delay}s..."
                )
                time.sleep(retry_delay)
                continue

            raise

    return {}


def upsert_game_stat(
    conn,
    fantasy_game_id: int,
    source_player_id: int,
    team_id: int,
    stats: dict,
) -> str:
    """
    Insere ou atualiza a estatística de um jogador em um confronto.

    Retorna 'inserted' ou 'updated'.
    """
    existing_stat = conn.execute(
        text(
            """
            SELECT fantasy_game_stat_id
            FROM fantasy_game_stats
            WHERE fantasy_game_id = :fantasy_game_id
              AND source_player_id = :source_player_id
            LIMIT 1
            """
        ),
        {
            "fantasy_game_id": fantasy_game_id,
            "source_player_id": source_player_id,
        },
    ).fetchone()

    params = {
        "fantasy_game_id": fantasy_game_id,
        "source_player_id": source_player_id,
        "team_id": team_id,
        "pts": stats.get("pts", 0.0),
        "reb": stats.get("reb", 0.0),
        "ast": stats.get("ast", 0.0),
        "stl": stats.get("stl", 0.0),
        "blk": stats.get("blk", 0.0),
        "three_pt": stats.get("three_pt", 0.0),
        "turnovers": stats.get("turnovers", 0.0),
        "source_file": "google_sheets",
    }

    if existing_stat:
        conn.execute(
            text(
                """
                UPDATE fantasy_game_stats
                SET team_id = :team_id,
                    pts = :pts,
                    reb = :reb,
                    ast = :ast,
                    stl = :stl,
                    blk = :blk,
                    three_pt = :three_pt,
                    turnovers = :turnovers,
                    source_file = :source_file,
                    updated_at = NOW()
                WHERE fantasy_game_id = :fantasy_game_id
                  AND source_player_id = :source_player_id
                """
            ),
            params,
        )

        return "updated"

    conn.execute(
        text(
            """
            INSERT INTO fantasy_game_stats (
                fantasy_game_id,
                source_player_id,
                team_id,
                pts,
                reb,
                ast,
                stl,
                blk,
                three_pt,
                turnovers,
                source_file,
                imported_at
            )
            VALUES (
                :fantasy_game_id,
                :source_player_id,
                :team_id,
                :pts,
                :reb,
                :ast,
                :stl,
                :blk,
                :three_pt,
                :turnovers,
                :source_file,
                NOW()
            )
            """
        ),
        params,
    )

    return "inserted"


# ============================================================================
# IMPORTAÇÃO
# ============================================================================

def import_only_stats() -> None:
    print("Autenticando com Google Sheets API...")

    creds = service_account.Credentials.from_service_account_file(
        SERVICE_ACCOUNT_FILE,
        scopes=SCOPES,
    )

    service = build("sheets", "v4", credentials=creds)

    urls_data = parse_urls_file(URLS_FILE)

    print(f"Encontradas {len(urls_data)} planilhas para importar.\n")

    stats_inserted = 0
    stats_updated = 0
    games_not_found = 0
    games_skipped_incomplete = 0
    players_not_found = 0

    with engine.begin() as conn:
        for url_info in urls_data:
            rodada = url_info["rodada"]
            spreadsheet_id = extract_spreadsheet_id(url_info["url"])
            round_num = get_round_number(rodada)

            print(f"Processando {rodada} ({spreadsheet_id})...")

            try:
                spreadsheet = fetch_with_retry_metadata(service, spreadsheet_id)
            except Exception as error:
                print(f"  Erro ao obter metadata: {error}\n")
                continue

            sheets = spreadsheet.get("sheets", [])

            if not sheets:
                print("  Nenhum sheet encontrado. Pulando.\n")
                continue

            for sheet in sheets:
                sheet_name = sheet["properties"]["title"]

                print(f"  Processando aba: {sheet_name}")

                if " x " not in sheet_name:
                    print("    Formato de aba inválido. Pulando.\n")
                    continue

                team_a_sigla = get_team_sigla_from_aba(sheet_name, "A")
                team_b_sigla = get_team_sigla_from_aba(sheet_name, "B")

                team_a_id = SIGLA_TO_TEAM_ID.get(team_a_sigla)
                team_b_id = SIGLA_TO_TEAM_ID.get(team_b_sigla)

                if team_a_id is None or team_b_id is None:
                    print(
                        f"    Sigla não mapeada: "
                        f"{team_a_sigla} x {team_b_sigla}. Pulando.\n"
                    )
                    continue

                range_name = f"'{sheet_name}'!A1:Z20"

                try:
                    values = fetch_with_retry(
                        service,
                        spreadsheet_id,
                        range_name,
                    )
                except Exception as error:
                    print(f"    Erro ao ler aba: {error}\n")
                    continue

                if len(values) < 18:
                    games_skipped_incomplete += 1
                    print("    Estrutura incompleta. Jogo ignorado.\n")
                    continue

                headers_a = values[1] if len(values) > 1 else []
                headers_b = values[11] if len(values) > 11 else []

                col_indices_a = map_header_columns(headers_a)
                col_indices_b = map_header_columns(headers_b)

                required_columns = {"player_name", *STAT_COLUMNS}

                missing_a = required_columns - set(col_indices_a)
                missing_b = required_columns - set(col_indices_b)

                if missing_a or missing_b:
                    print(
                        "    Cabeçalhos obrigatórios não encontrados. "
                        f"Time A faltando: {sorted(missing_a)}; "
                        f"Time B faltando: {sorted(missing_b)}. Pulando.\n"
                    )
                    continue

                team_a_players, team_a_has_filled_stats = parse_team_data(
                    values=values,
                    start_row=2,
                    col_indices=col_indices_a,
                    conn=conn,
                    team_id=team_a_id,
                )

                team_b_players, team_b_has_filled_stats = parse_team_data(
                    values=values,
                    start_row=12,
                    col_indices=col_indices_b,
                    conn=conn,
                    team_id=team_b_id,
                )

                # O confronto só entra no banco quando os dois lados têm dados.
                if not team_a_has_filled_stats or not team_b_has_filled_stats:
                    games_skipped_incomplete += 1

                    if not team_a_has_filled_stats and not team_b_has_filled_stats:
                        reason = "ambos os times estão sem stats preenchidas"
                    elif not team_a_has_filled_stats:
                        reason = f"{team_a_sigla} está sem stats preenchidas"
                    else:
                        reason = f"{team_b_sigla} está sem stats preenchidas"

                    print(
                        f"    Jogo não realizado ou incompleto: {reason}. "
                        "Nenhuma stat foi gravada.\n"
                    )
                    continue

                if not team_a_players or not team_b_players:
                    games_skipped_incomplete += 1
                    print(
                        "    Dados encontrados na planilha, mas não houve jogadores "
                        "reconhecidos nos dois lados. Nenhuma stat foi gravada.\n"
                    )
                    continue

                fantasy_game_id = get_fantasy_game_id_by_teams(
                    round_num=round_num,
                    team_a_id=team_a_id,
                    team_b_id=team_b_id,
                    conn=conn,
                )

                if fantasy_game_id is None:
                    games_not_found += 1
                    print(
                        f"    Jogo não encontrado em fantasy_games "
                        f"(rodada={round_num}, times={team_a_id} x {team_b_id}). "
                        "Pulando.\n"
                    )
                    continue

                print(
                    f"    Jogo encontrado: ID={fantasy_game_id} "
                    f"({team_a_sigla} x {team_b_sigla})"
                )

                processed_players = 0

                for player in team_a_players + team_b_players:
                    action = upsert_game_stat(
                        conn=conn,
                        fantasy_game_id=fantasy_game_id,
                        source_player_id=player["source_player_id"],
                        team_id=player["team_id"],
                        stats=player["stats"],
                    )

                    if action == "inserted":
                        stats_inserted += 1
                    else:
                        stats_updated += 1

                    processed_players += 1

                print(
                    f"    {processed_players} jogadores inseridos/atualizados.\n"
                )

    print("=" * 60)
    print("Importação concluída!")
    print(f"  Stats inseridos: {stats_inserted}")
    print(f"  Stats atualizados: {stats_updated}")
    print(f"  Jogos ignorados (vazios/incompletos): {games_skipped_incomplete}")
    print(f"  Jogos não encontrados: {games_not_found}")
    print(f"  Jogadores não encontrados: {players_not_found}")


if __name__ == "__main__":
    import_only_stats()