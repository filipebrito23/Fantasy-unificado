import os
import re
import time
from pathlib import Path

import gspread
import pandas as pd
import psycopg2
from dotenv import load_dotenv
from google.oauth2.service_account import Credentials

load_dotenv()

DATABASE_URL = os.getenv("DATABASE_URL")
SERVICE_ACCOUNT_FILE = Path(__file__).resolve().parent / "service_account.json"

SCOPES = [
    "https://www.googleapis.com/auth/spreadsheets",
    "https://www.googleapis.com/auth/drive",
]

COLUNA_GAMEID = "GameID"
COLUNA_JOGADOR = "Jogadores"


def normalizar_url_psycopg2(url):
    return url.replace("postgresql+psycopg2://", "postgresql://")


def extrair_spreadsheet_id(link):
    match = re.search(r"/d/([a-zA-Z0-9-_]+)", link)
    if match:
        return match.group(1)

    match = re.search(r"key=([a-zA-Z0-9-_]+)", link)
    if match:
        return match.group(1)

    raise ValueError("Não foi possível extrair o Spreadsheet ID do link.")


def conectar_gsheets():
    if not SERVICE_ACCOUNT_FILE.exists():
        raise FileNotFoundError("service_account.json não encontrado.")

    creds = Credentials.from_service_account_file(
        str(SERVICE_ACCOUNT_FILE),
        scopes=SCOPES
    )

    return gspread.authorize(creds)


def carregar_calendario():
    conn = psycopg2.connect(normalizar_url_psycopg2(DATABASE_URL))
    cur = conn.cursor()

    cur.execute("""
        SELECT
            nba_team_abbr,
            week_number,
            game_number_in_week,
            nba_game_id
        FROM fantasy_schedule;
    """)

    registros = cur.fetchall()

    cur.close()
    conn.close()

    calendario = {}

    for team, semana_num, jogo_na_semana, game_id in registros:
        if game_id is None:
            continue

        chave = (
            str(team).upper(),
            int(semana_num),
            int(jogo_na_semana)
        )

        calendario[chave] = str(game_id).zfill(10)

    return calendario


def achar_gameid(calendario, nba_team, semana, jogo_semana):
    nba_team = str(nba_team).upper()
    semana = int(semana)
    jogo_semana = int(jogo_semana)

    chave = (nba_team, semana, jogo_semana)

    if chave in calendario:
        return calendario[chave]

    # Regra: se o time tiver só 2 jogos, o jogo 3 usa o último disponível
    if jogo_semana == 3:
        for fallback in (2, 1):
            chave_fallback = (nba_team, semana, fallback)
            if chave_fallback in calendario:
                return calendario[chave_fallback]

    return None


def obter_mapa_jogador_time():
    conn = psycopg2.connect(normalizar_url_psycopg2(DATABASE_URL))
    cur = conn.cursor()

    cur.execute("""
        SELECT
            player_name,
            nba_team
        FROM fantasy_players
        WHERE nba_team IS NOT NULL
          AND nba_team <> '';
    """)

    registros = cur.fetchall()

    cur.close()
    conn.close()

    mapa = {}

    for player_name, nba_team in registros:
        chave = normalizar_nome(player_name)
        mapa[chave] = str(nba_team).upper()

    return mapa


def normalizar_nome(nome):
    if nome is None:
        return ""

    nome = str(nome).strip().lower()
    nome = re.sub(r"[*\\.]", "", nome)
    return re.sub(r"\s+", " ", nome)


def a1_col(col_num):
    result = ""
    while col_num > 0:
        col_num, remainder = divmod(col_num - 1, 26)
        result = chr(65 + remainder) + result
    return result


def processar_planilha(spreadsheet_id, semana, jogo_semana):
    client = conectar_gsheets()
    spreadsheet = client.open_by_key(spreadsheet_id)

    calendario = carregar_calendario()
    mapa_jogador_time = obter_mapa_jogador_time()

    worksheets = spreadsheet.worksheets()

    resumo = []

    for ws in worksheets:
        all_values = ws.get_all_values()

        if not all_values:
            continue

        header_row_idx = None

        for idx, row in enumerate(all_values):
            row_norm = [str(v).strip() for v in row]

            if COLUNA_JOGADOR in row_norm and COLUNA_GAMEID in row_norm:
                header_row_idx = idx
                break

        if header_row_idx is None:
            continue

        header = all_values[header_row_idx]

        try:
            idx_jogador = header.index(COLUNA_JOGADOR) + 1
            idx_gameid = header.index(COLUNA_GAMEID) + 1
        except ValueError:
            continue

        updates = []
        preenchidos = 0
        nao_encontrados = 0

        for i, row in enumerate(all_values[header_row_idx + 1:], start=header_row_idx + 2):
            if len(row) <= max(idx_jogador, idx_gameid) - 1:
                continue

            jogador = str(row[idx_jogador - 1]).strip()
            gameid_atual = str(row[idx_gameid - 1]).strip()

            if not jogador:
                continue

            if gameid_atual:
                continue

            nba_team = mapa_jogador_time.get(normalizar_nome(jogador))

            if not nba_team:
                nao_encontrados += 1
                continue

            game_id = achar_gameid(
                calendario,
                nba_team,
                semana,
                jogo_semana
            )

            if not game_id:
                nao_encontrados += 1
                continue

            cell = f"{a1_col(idx_gameid)}{i}"

            updates.append({
                "range": cell,
                "values": [[game_id]]
            })

            preenchidos += 1

        if updates:
            ws.batch_update(updates)

        resumo.append({
            "aba": ws.title,
            "gameids_preenchidos": preenchidos,
            "jogadores_sem_time_ou_gameid": nao_encontrados
        })

    return resumo


def main():
    print("=== Preencher GameID por semana e jogo da semana ===")

    link = input("Cole o link da planilha: ").strip()
    semana = int(input("Digite o número da semana: ").strip())
    jogo_semana = int(input("Digite o número do jogo na semana (1, 2 ou 3): ").strip())

    if jogo_semana not in (1, 2, 3):
        raise ValueError("O número do jogo na semana deve ser 1, 2 ou 3.")

    spreadsheet_id = extrair_spreadsheet_id(link)

    print(f"\nPlanilha: {spreadsheet_id}")
    print(f"Semana: {semana}")
    print(f"Jogo na semana: {jogo_semana}")

    resumo = processar_planilha(
        spreadsheet_id,
        semana,
        jogo_semana
    )

    print("\nRESUMO:")
    for item in resumo:
        print(item)


if __name__ == "__main__":
    main()