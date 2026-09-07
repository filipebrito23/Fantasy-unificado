"""
Feature 2b - Importacao APENAS de stats dos jogadores
"""

import json
import re
import time
from pathlib import Path
from google.oauth2 import service_account
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError
from sqlalchemy import text
from app_lib.db_v5 import engine


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

MAX_RETRIES = 3
RETRY_DELAY = 5

# Mapeamento sigla → team_id (CORRIGIDO)
SIGLA_TO_TEAM_ID = {
    "ABB": 1,   # Alabama Black Bears
    "FRC": 2,   # Franca Celtics
    "GUA": 3,   # Guarulhos Nuggets
    "IRB": 4,   # Itajubá±±Rabbits
    "KDG": 5,   # Kaipiras da Gema
    "MIB": 6,   # Miami Barons
    "MNT": 7,   # Montreal Turtles
    "NOD": 8,   # New Orleans Dancers
    "OSA": 9,   # Osasco Heat
    "PVK": 10,  # Pelotas Vikings
    "PER": 11,  # Pernambuco Pharynx
    "RBD": 12,  # RJ Black Mamba (CORRIGIDO: era 13)
    "RBM": 13,  # Recife Black Diamond (CORRIGIDO: era 12)
    "TCH": 14,  # Tcheltics da Peleia
}


def extract_spreadsheet_id(url: str) -> str:
    match = re.search(r"/spreadsheets/d/([a-zA-Z0-9_-]+)", url)
    if match:
        return match.group(1)
    raise ValueError(f"URL invalida: {url}")


def parse_urls_file(filepath: Path) -> list[dict]:
    urls = []
    with open(filepath, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            parts = line.split(" - ", 1)
            if len(parts) == 2:
                rodada = parts[0].strip()
                url = parts[1].strip()
                urls.append({"rodada": rodada, "url": url})
    return urls


def get_team_sigla_from_aba(aba_name: str, team_position: str) -> str:
    parts = aba_name.split(" x ")
    if len(parts) == 2:
        return parts[0].strip() if team_position == "A" else parts[1].strip()
    return aba_name.strip()


def get_fantasy_game_id_by_teams(round_num: int, team_a_id: int, team_b_id: int, conn) -> int | None:
    """Busca fantasy_game_id por round + team_ids (QUALQUER ORDEM)."""
    
    # ORDEM 1: team_a_id = team_1_id, team_b_id = team_2_id
    result = conn.execute(
        text(
            """
            SELECT fantasy_game_id
            FROM fantasy_games
            WHERE round = :round
              AND team_1_id = :team_a_id
              AND team_2_id = :team_b_id
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
        print(f"      (encontrado na ordem 1: {team_a_id} x {team_b_id})")
        return row[0]
    
    # ORDEM 2: team_a_id = team_2_id, team_b_id = team_1_id (invertida)
    result = conn.execute(
        text(
            """
            SELECT fantasy_game_id
            FROM fantasy_games
            WHERE round = :round
              AND team_1_id = :team_b_id
              AND team_2_id = :team_a_id
            LIMIT 1
            """
        ),
        {
            "round": round_num,
            "team_b_id": team_b_id,
            "team_a_id": team_a_id,
        },
    )
    row = result.fetchone()
    if row:
        print(f"      (encontrado na ordem 2: {team_b_id} x {team_a_id})")
        return row[0]
    
    return None


def get_player_source_id(player_name: str, conn) -> int | None:
    result = conn.execute(
        text(
            """
            SELECT source_player_id
            FROM fantasy_players
            WHERE player_name = :player_name
            LIMIT 1
            """
        ),
        {"player_name": player_name},
    )
    row = result.fetchone()
    return row[0] if row else None


def parse_team_data(values: list, start_row: int, col_indices: dict, conn, team_id: int) -> list[dict]:
    players = []
    
    for row_idx in range(start_row, start_row + 6):
        if row_idx >= len(values):
            break
        row = values[row_idx]
        
        if not row or not row[0].strip():
            continue
        if "total" in row[0].strip().lower():
            continue
        
        if "player_name" not in col_indices:
            continue
        
        name_col = col_indices["player_name"]
        if name_col >= len(row):
            continue
            
        player_name = row[name_col].strip()
        
        if not player_name:
            continue
        
        stats = {}
        for stat_name, col_idx in col_indices.items():
            if stat_name == "player_name":
                continue
            if col_idx < len(row):
                try:
                    stats[stat_name] = float(row[col_idx])
                except (ValueError, TypeError):
                    stats[stat_name] = 0
            else:
                stats[stat_name] = 0
        
        source_player_id = get_player_source_id(player_name, conn)
        
        if source_player_id is None:
            print(f"      Jogador nao encontrado: {player_name}")
            continue
        
        players.append({
            "source_player_id": source_player_id,
            "team_id": team_id,
            "stats": stats,
        })
    
    return players


def fetch_with_retry(service, spreadsheet_id: str, range_name: str, max_retries: int = MAX_RETRIES, retry_delay: int = RETRY_DELAY):
    for attempt in range(1, max_retries + 1):
        try:
            result = service.spreadsheets().values().get(
                spreadsheetId=spreadsheet_id,
                range=range_name
            ).execute()
            return result.get("values", [])
        except HttpError as e:
            if e.resp.status == 503 and attempt < max_retries:
                print(f"      Erro 503. Tentativa {attempt}/{max_retries}. Aguardando {retry_delay}s...")
                time.sleep(retry_delay)
            else:
                raise
    return []


def fetch_with_retry_metadata(service, spreadsheet_id: str, max_retries: int = MAX_RETRIES, retry_delay: int = RETRY_DELAY):
    for attempt in range(1, max_retries + 1):
        try:
            return service.spreadsheets().get(spreadsheetId=spreadsheet_id).execute()
        except HttpError as e:
            if e.resp.status == 503 and attempt < max_retries:
                print(f"  Erro 503. Tentativa {attempt}/{max_retries}. Aguardando {retry_delay}s...")
                time.sleep(retry_delay)
            else:
                raise
    return {}


def import_only_stats():
    print("Autenticando com Google Sheets API...")
    creds = service_account.Credentials.from_service_account_file(
        SERVICE_ACCOUNT_FILE, scopes=SCOPES
    )
    service = build("sheets", "v4", credentials=creds)
    
    urls_data = parse_urls_file(URLS_FILE)
    print(f"Encontradas {len(urls_data)} planilhas para importar.\n")
    
    stats_inserted = 0
    stats_updated = 0
    games_not_found = 0
    
    with engine.begin() as conn:
        
        for url_info in urls_data:
            rodada = url_info["rodada"]
            url = url_info["url"]
            spreadsheet_id = extract_spreadsheet_id(url)
            
            print(f"Processando {rodada} ({spreadsheet_id})...")
            
            try:
                spreadsheet = fetch_with_retry_metadata(service, spreadsheet_id)
            except Exception as e:
                print(f"  Erro ao obter metadata: {e}\n")
                continue
            
            sheets = spreadsheet.get("sheets", [])
            
            if not sheets:
                print(f"  Nenhum sheet encontrado. Pulando.\n")
                continue
            
            for sheet in sheets:
                sheet_name = sheet["properties"]["title"]
                
                print(f"  Processando aba: {sheet_name}")
                
                if " x " not in sheet_name:
                    print(f"    Formato de aba invalido. Pulando.\n")
                    continue
                
                team_a_sigla = get_team_sigla_from_aba(sheet_name, "A")
                team_b_sigla = get_team_sigla_from_aba(sheet_name, "B")
                
                team_a_id = SIGLA_TO_TEAM_ID.get(team_a_sigla)
                team_b_id = SIGLA_TO_TEAM_ID.get(team_b_sigla)
                
                if team_a_id is None or team_b_id is None:
                    print(f"    Sigla nao mapeada. Pulando.\n")
                    continue
                
                print(f"    Times IDs: {team_a_id} ({team_a_sigla}) x {team_b_id} ({team_b_sigla})")
                
                round_num = int(rodada.replace("Jogo ", ""))
                fantasy_game_id = get_fantasy_game_id_by_teams(round_num, team_a_id, team_b_id, conn)
                
                if fantasy_game_id is None:
                    print(f"    Jogo NAO encontrado (round={round_num}, teams={team_a_id} x {team_b_id}). Pulando.\n")
                    games_not_found += 1
                    continue
                
                print(f"    Jogo encontrado: ID={fantasy_game_id}")
                
                range_name = f"{sheet_name}!A1:Z20"
                
                try:
                    values = fetch_with_retry(service, spreadsheet_id, range_name)
                except Exception as e:
                    print(f"    Erro ao ler aba: {e}\n")
                    continue
                
                if len(values) < 18:
                    print(f"    Dados insuficientes. Pulando.\n")
                    continue
                
                # Time A
                headers_a = values[1] if len(values) > 1 else []
                
                col_indices = {}
                for i, header in enumerate(headers_a):
                    header_clean = header.strip().lower()
                    for key, value in COLUMN_MAP.items():
                        if key in header_clean or header_clean in key:
                            col_indices[value] = i
                            break
                
                if "player_name" not in col_indices:
                    print(f"    Coluna 'Jogadores' nao encontrada. Pulando.\n")
                    continue
                
                team_a_players = parse_team_data(values, start_row=2, col_indices=col_indices, conn=conn, team_id=team_a_id)
                
                if not team_a_players:
                    print(f"    Nenhum jogador Time A. Pulando.\n")
                    continue
                
                # Time B
                headers_b = values[11] if len(values) > 11 else []
                
                col_indices_b = {}
                for i, header in enumerate(headers_b):
                    header_clean = header.strip().lower()
                    for key, value in COLUMN_MAP.items():
                        if key in header_clean or header_clean in key:
                            col_indices_b[value] = i
                            break
                
                team_b_players = parse_team_data(values, start_row=12, col_indices=col_indices_b, conn=conn, team_id=team_b_id)
                
                if not team_b_players:
                    print(f"    Nenhum jogador Time B. Pulando.\n")
                    continue
                
                # Inserir/atualizar stats
                all_players = team_a_players + team_b_players
                
                for player in all_players:
                    stats = player["stats"]
                    
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
                            "source_player_id": player["source_player_id"],
                        },
                    ).fetchone()
                    
                    if existing_stat:
                        conn.execute(
                            text(
                                """
                                UPDATE fantasy_game_stats
                                SET pts = :pts,
                                    reb = :reb,
                                    ast = :ast,
                                    stl = :stl,
                                    blk = :blk,
                                    three_pt = :three_pt,
                                    turnovers = :turnovers,
                                    updated_at = NOW()
                                WHERE fantasy_game_id = :fantasy_game_id
                                  AND source_player_id = :source_player_id
                                """
                            ),
                            {
                                "pts": stats.get("pts", 0),
                                "reb": stats.get("reb", 0),
                                "ast": stats.get("ast", 0),
                                "stl": stats.get("stl", 0),
                                "blk": stats.get("blk", 0),
                                "three_pt": stats.get("three_pt", 0),
                                "turnovers": stats.get("turnovers", 0),
                                "fantasy_game_id": fantasy_game_id,
                                "source_player_id": player["source_player_id"],
                            },
                        )
                        stats_updated += 1
                    else:
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
                            {
                                "fantasy_game_id": fantasy_game_id,
                                "source_player_id": player["source_player_id"],
                                "team_id": player["team_id"],
                                "pts": stats.get("pts", 0),
                                "reb": stats.get("reb", 0),
                                "ast": stats.get("ast", 0),
                                "stl": stats.get("stl", 0),
                                "blk": stats.get("blk", 0),
                                "three_pt": stats.get("three_pt", 0),
                                "turnovers": stats.get("turnovers", 0),
                                "source_file": "google_sheets",
                            },
                        )
                        stats_inserted += 1
                
                print(f"    {len(all_players)} jogadores processados.\n")
    
    print(f"Importacao concluida!")
    print(f"  Stats inseridos: {stats_inserted}")
    print(f"  Stats atualizados: {stats_updated}")
    print(f"  Jogos nao encontrados: {games_not_found}")


if __name__ == "__main__":
    import_only_stats()