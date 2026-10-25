import os
import re
import time

import psycopg2
from dotenv import load_dotenv

from nba_api.stats.endpoints import commonplayerinfo
from nba_api.stats.static import players


load_dotenv()

DATABASE_URL = os.getenv("DATABASE_URL")

if not DATABASE_URL:
    raise ValueError("DATABASE_URL não encontrada no .env")


def normalizar_url_psycopg2(url: str) -> str:
    """
    Aceita a mesma DATABASE_URL usada pelo SQLAlchemy:
    postgresql+psycopg2://usuario:senha@host/db?sslmode=require

    E converte para o formato aceito pelo psycopg2:
    postgresql://usuario:senha@host/db?sslmode=require
    """
    return url.replace("postgresql+psycopg2://", "postgresql://")


def normalizar_nome(nome):
    if nome is None:
        return ""

    nome = str(nome).strip().lower()
    nome = re.sub(r"[^a-zà-ú\s]", "", nome)
    return re.sub(r"\s+", " ", nome).strip()


def buscar_jogadores_sem_time(cur):
    cur.execute("""
        SELECT
            fantasy_player_id,
            player_name,
            nba_team
        FROM fantasy_players
        WHERE nba_team IS NULL
           OR nba_team = ''
        ORDER BY fantasy_player_id;
    """)

    return cur.fetchall()


def encontrar_jogador_nba(nome):
    nome_norm = normalizar_nome(nome)

    candidatos = players.find_players_by_full_name(nome_norm)

    if not candidatos:
        return None

    if len(candidatos) == 1:
        return candidatos[0]

    ativos = [
        p for p in candidatos
        if str(p.get("is_active", "")).lower() in ("true", "1")
    ]

    if len(ativos) == 1:
        return ativos[0]

    return None


def obter_time_nba(player_id):
    info = commonplayerinfo.CommonPlayerInfo(player_id=player_id)
    dados = info.get_normalized_dict()
    comum = dados.get("CommonPlayerInfo", [])

    if not comum:
        return None

    return comum[0].get("TEAM_ABBREVIATION")


def main():
    url_psycopg2 = normalizar_url_psycopg2(DATABASE_URL)

    conn = psycopg2.connect(url_psycopg2)
    cur = conn.cursor()

    jogadores = buscar_jogadores_sem_time(cur)

    print(f"Jogadores sem nba_team: {len(jogadores)}")

    atualizados = 0
    nao_encontrados = 0
    erros = 0

    for fantasy_player_id, player_name, nba_team_atual in jogadores:
        jogador_nba = encontrar_jogador_nba(player_name)

        if not jogador_nba:
            print(f"[NAO ENCONTRADO] {player_name}")
            nao_encontrados += 1
            continue

        try:
            team_abbr = obter_time_nba(jogador_nba["id"])

            if not team_abbr:
                print(f"[SEM TIME] {player_name} -> {jogador_nba['full_name']}")
                nao_encontrados += 1
                continue

            cur.execute("""
                UPDATE fantasy_players
                SET nba_team = %s,
                    updated_at = now()
                WHERE fantasy_player_id = %s;
            """, (team_abbr, fantasy_player_id))

            conn.commit()

            atualizados += 1
            print(f"[OK] {player_name} -> {team_abbr}")

            time.sleep(0.6)

        except Exception as exc:
            print(f"[ERRO] {player_name}: {exc}")
            erros += 1
            conn.rollback()
            time.sleep(1)

    print("\nRESUMO")
    print(f"Atualizados: {atualizados}")
    print(f"Não encontrados/sem time: {nao_encontrados}")
    print(f"Erros: {erros}")

    cur.close()
    conn.close()


if __name__ == "__main__":
    main()