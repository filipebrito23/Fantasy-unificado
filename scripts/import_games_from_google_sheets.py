"""
Feature 2 - Importacao de jogos do Google Planilhas
PNBC+ Features Avanadas

Este script le as planilhas de jogos do Google Drive e importa para o Neon:
- fantasy_games (jogos realizados)
- fantasy_game_stats (estatisticas individuais por jogador)

Estrutura das planilhas:
- 39 arquivos (um por rodada)
- Cada arquivo tem 7 abas (uma por jogo)
- Cada aba tem:
  - Linha 1: Nome do Time A
  - Linha 2: Titulos das colunas
  - Linhas 3-8: 6 jogadores do Time A
  - Linha 9: Total (ignorar)
  - Linha 10: Em branco (ignorar)
  - Linha 11: Nome do Time B
  - Linha 12: Titulos das colunas
  - Linhas 13-18: 6 jogadores do Time B
  - Linha 19: Total (ignorar)
  - Linha 20: Em branco (ignorar)
"""

import json
import re
from pathlib import Path
from google.oauth2 import service_account
from googleapiclient.discovery import build
from sqlalchemy import text
from app_lib.db_v5 import engine


# ============================================================================
# CONFIGURACAO
# ============================================================================

SERVICE_ACCOUNT_FILE = Path(__file__).parent / "service_account.json"
URLS_FILE = Path(__file__).parent / "url-2.txt"

# Escopos necessarios para ler planilhas
SCOPES = ["https://www.googleapis.com/auth/spreadsheets.readonly"]

# Mapeamento de colunas (nomes exatos das colunas nas planilhas)
COLUMN_MAP = {
    "Nome": "player_name",
    "Pontos": "pts",
    "Rebotes": "reb",
    "Assistencias": "ast",
    "Roubos": "stl",
    "Tocos": "blk",
    "Bolas de 3": "three_pt",
    "Turnovers": "turnovers",
}


# ============================================================================
# FUNCOES AUXILIARES
# ============================================================================


def extract_spreadsheet_id(url: str) -> str:
    """Extrai o ID da planilha de uma URL do Google Sheets."""
    match = re.search(r"/spreadsheets/d/([a-zA-Z0-9_-]+)", url)
    if match:
        return match.group(1)
    raise ValueError(f"URL invalida: {url}")


def parse_urls_file(filepath: Path) -> list[dict]:
    """Le o arquivo de URLs e retorna uma lista de dicionarios com rodada e URL."""
    urls = []
    with open(filepath, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            # Formato: "Jogo 1 - https://..."
            parts = line.split(" - ", 1)
            if len(parts) == 2:
                rodada = parts[0].strip()
                url = parts[1].strip()
                urls.append({"rodada": rodada, "url": url})
    return urls


def get_team_name_from_aba(aba_name: str, team_position: str) -> str:
    """Extrai o nome do time a partir do nome da aba.
    
    Exemplo: 'KDG x MNT' -> 'KDG' ou 'MNT'
    team_position: 'A' ou 'B'
    """
    parts = aba_name.split(" x ")
    if len(parts) == 2:
        return parts[0].strip() if team_position == "A" else parts[1].strip()
    return aba_name.strip()


def calculate_efficiency(stats: dict) -> float:
    """Calcula a eficiencia de um jogador com base na formula:
    1.5*PTS + 3.5*REB + 4.0*AST + 5.0*STL + 5.0*BLK + 3.5*3PT - 3.5*TO
    """
    return (
        1.5 * stats.get("pts", 0)
        + 3.5 * stats.get("reb", 0)
        + 4.0 * stats.get("ast", 0)
        + 5.0 * stats.get("stl", 0)
        + 5.0 * stats.get("blk", 0)
        + 3.5 * stats.get("three_pt", 0)
        - 3.5 * stats.get("turnovers", 0)
    )


def determine_category_winner(
    team_a_value: float, team_b_value: float, category: str
) -> str:
    """Determina o vencedor de uma categoria.
    
    Para TO (turnovers), menor valor vence.
    Para as demais, maior valor vence.
    """
    if category == "turnovers":
        if team_a_value < team_b_value:
            return "A"
        elif team_b_value < team_a_value:
            return "B"
        else:
            return "tie"
    else:
        if team_a_value > team_b_value:
            return "A"
        elif team_b_value > team_a_value:
            return "B"
        else:
            return "tie"


def get_player_source_id(player_name: str, conn) -> int | None:
    """Busca o source_player_id com base no nome do jogador."""
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


def get_team_id(team_name: str, conn) -> int | None:
    """Busca o team_id com base no nome do time."""
    result = conn.execute(
        text(
            """
            SELECT team_id
            FROM teams
            WHERE team_name = :team_name
            LIMIT 1
            """
        ),
        {"team_name": team_name},
    )
    row = result.fetchone()
    return row[0] if row else None


# ============================================================================
# IMPORTACAO
# ============================================================================


def import_games_from_google_sheets():
    """Funcao principal de importacao."""
    
    # Autenticacao
    print("Autenticando com Google Sheets API...")
    creds = service_account.Credentials.from_service_account_file(
        SERVICE_ACCOUNT_FILE, scopes=SCOPES
    )
    service = build("sheets", "v4", credentials=creds)
    
    # Ler URLs
    urls_data = parse_urls_file(URLS_FILE)
    print(f"Encontradas {len(urls_data)} planilhas para importar.\n")
    
    with engine.begin() as conn:
        
        for url_info in urls_data:
            rodada = url_info["rodada"]
            url = url_info["url"]
            spreadsheet_id = extract_spreadsheet_id(url)
            
            print(f"Processando {rodada} ({spreadsheet_id})...")
            
            # Obter metadata da planilha
            spreadsheet = service.spreadsheets().get(
                spreadsheetId=spreadsheet_id
            ).execute()
            
            sheets = spreadsheet.get("sheets", [])
            
            if not sheets:
                print(f"  Nenhum sheet encontrado. Pulando.\n")
                continue
            
            # Processar cada aba (jogo)
            for sheet in sheets:
                sheet_name = sheet["properties"]["title"]
                sheet_id = sheet["properties"]["sheetId"]
                
                print(f"  Processando aba: {sheet_name}")
                
                # Extrair nomes dos times da aba
                # Exemplo: 'KDG x MNT'
                if " x " not in sheet_name:
                    print(f"    Formato de aba invalido. Pulando.\n")
                    continue
                
                team_a_name = get_team_name_from_aba(sheet_name, "A")
                team_b_name = get_team_name_from_aba(sheet_name, "B")
                
                # Buscar team_ids
                team_a_id = get_team_id(team_a_name, conn)
                team_b_id = get_team_id(team_b_name, conn)
                
                if team_a_id is None or team_b_id is None:
                    print(f"    Times nao encontrados no banco. Pulando.\n")
                    continue
                
                # Ler dados da aba
                # Range: linhas 1-20, todas as colunas
                range_name = f"{sheet_name}!A1:Z20"
                
                try:
                    result = service.spreadsheets().values().get(
                        spreadsheetId=spreadsheet_id,
                        range=range_name
                    ).execute()
                    values = result.get("values", [])
                except Exception as e:
                    print(f"    Erro ao ler aba: {e}\n")
                    continue
                
                if len(values) < 18:
                    print(f"    Dados insuficientes na aba. Pulando.\n")
                    continue
                
                # Linha 1: Time A (ja temos)
                # Linha 2: Titulos das colunas
                headers = values[1] if len(values) > 1 else []
                
                # Mapear indices das colunas
                col_indices = {}
                for i, header in enumerate(headers):
                    header_clean = header.strip()
                    for key, value in COLUMN_MAP.items():
                        if key.lower() in header_clean.lower() or header_clean.lower() in key.lower():
                            col_indices[value] = i
                            break
                
                if "player_name" not in col_indices:
                    print(f"    Coluna 'Nome' nao encontrada. Pulando.\n")
                    continue
                
                # Linhas 3-8: Jogadores do Time A
                team_a_players = []
                for row_idx in range(2, 8):  # indices 2-7 (linhas 3-8)
                    if row_idx >= len(values):
                        break
                    row = values[row_idx]
                    if not row or not row[0].strip():
                        continue
                    
                    player_name = row[col_indices["player_name"]].strip()
                    
                    stats = {}
                    for stat_name, col_idx in col_indices.items():
                        if col_idx < len(row):
                            try:
                                stats[stat_name] = float(row[col_idx])
                            except (ValueError, TypeError):
                                stats[stat_name] = 0
                        else:
                            stats[stat_name] = 0
                    
                    source_player_id = get_player_source_id(player_name, conn)
                    
                    if source_player_id is None:
                        print(f"    Jogador nao encontrado: {player_name}")
                        continue
                    
                    team_a_players.append({
                        "source_player_id": source_player_id,
                        "team_id": team_a_id,
                        "stats": stats,
                    })
                
                # Linhas 13-18: Jogadores do Time B
                team_b_players = []
                for row_idx in range(12, 18):  # indices 12-17 (linhas 13-18)
                    if row_idx >= len(values):
                        break
                    row = values[row_idx]
                    if not row or not row[0].strip():
                        continue
                    
                    player_name = row[col_indices["player_name"]].strip()
                    
                    stats = {}
                    for stat_name, col_idx in col_indices.items():
                        if col_idx < len(row):
                            try:
                                stats[stat_name] = float(row[col_idx])
                            except (ValueError, TypeError):
                                stats[stat_name] = 0
                        else:
                            stats[stat_name] = 0
                    
                    source_player_id = get_player_source_id(player_name, conn)
                    
                    if source_player_id is None:
                        print(f"    Jogador nao encontrado: {player_name}")
                        continue
                    
                    team_b_players.append({
                        "source_player_id": source_player_id,
                        "team_id": team_b_id,
                        "stats": stats,
                    })
                
                # Calcular totais por categoria para cada time
                categories = ["pts", "reb", "ast", "stl", "blk", "three_pt", "turnovers"]
                
                team_a_totals = {cat: sum(p["stats"].get(cat, 0) for p in team_a_players) for cat in categories}
                team_b_totals = {cat: sum(p["stats"].get(cat, 0) for p in team_b_players) for cat in categories}
                
                # Determinar vencedor de cada categoria
                category_wins = {"A": 0, "B": 0, "tie": 0}
                for cat in categories:
                    winner = determine_category_winner(
                        team_a_totals[cat], team_b_totals[cat], cat
                    )
                    category_wins[winner] += 1
                
                # Determinar vencedor do jogo
                if category_wins["A"] > category_wins["B"]:
                    winner = "A"
                elif category_wins["B"] > category_wins["A"]:
                    winner = "B"
                else:
                    winner = "tie"
                
                # Calcular team_1_points e team_2_points (soma de PTS)
                team_1_points = team_a_totals["pts"]
                team_2_points = team_b_totals["pts"]
                
                # Inserir em fantasy_games
                # Verificar se jogo ja existe
                existing_game = conn.execute(
                    text(
                        """
                        SELECT fantasy_game_id
                        FROM fantasy_games
                        WHERE team_1_id = :team_1_id
                          AND team_2_id = :team_2_id
                          AND round = :round
                        LIMIT 1
                        """
                    ),
                    {
                        "team_1_id": team_a_id,
                        "team_2_id": team_b_id,
                        "round": int(rodada.replace("Jogo ", "")),
                    },
                ).fetchone()
                
                if existing_game:
                    fantasy_game_id = existing_game[0]
                    print(f"    Jogo ja existe (ID: {fantasy_game_id}). Atualizando...")
                    
                    # Atualizar pontos
                    conn.execute(
                        text(
                            """
                            UPDATE fantasy_games
                            SET team_1_points = :team_1_points,
                                team_2_points = :team_2_points
                            WHERE fantasy_game_id = :fantasy_game_id
                            """
                        ),
                        {
                            "team_1_points": team_1_points,
                            "team_2_points": team_2_points,
                            "fantasy_game_id": fantasy_game_id,
                        },
                    )
                else:
                    # Inserir novo jogo
                    result = conn.execute(
                        text(
                            """
                            INSERT INTO fantasy_games (
                                source_game_id,
                                team_1_id,
                                team_1_name,
                                team_1_points,
                                team_2_points,
                                team_2_id,
                                team_2_name,
                                round,
                                source_file,
                                source_sheet,
                                imported_at,
                                updated_at
                            )
                            VALUES (
                                :source_game_id,
                                :team_1_id,
                                :team_1_name,
                                :team_1_points,
                                :team_2_points,
                                :team_2_id,
                                :team_2_name,
                                :round,
                                :source_file,
                                :source_sheet,
                                NOW(),
                                NOW()
                            )
                            RETURNING fantasy_game_id
                            """
                        ),
                        {
                            "source_game_id": int(rodada.replace("Jogo ", "")),
                            "team_1_id": team_a_id,
                            "team_1_name": team_a_name,
                            "team_1_points": team_1_points,
                            "team_2_points": team_2_points,
                            "team_2_id": team_b_id,
                            "team_2_name": team_b_name,
                            "round": int(rodada.replace("Jogo ", "")),
                            "source_file": "google_sheets",
                            "source_sheet": sheet_name,
                        },
                    )
                    fantasy_game_id = result.fetchone()[0]
                    print(f"    Jogo inserido (ID: {fantasy_game_id})")
                
                # Inserir em fantasy_game_stats
                all_players = team_a_players + team_b_players
                
                for player in all_players:
                    stats = player["stats"]
                    
                    # Verificar se ja existe
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
                        # Atualizar
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
                    else:
                        # Inserir
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
                
                print(f"    {len(all_players)} jogadores inseridos/atualizados.\n")
    
    print("Importacao concluida!")


if __name__ == "__main__":
    import_games_from_google_sheets()