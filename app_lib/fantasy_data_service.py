from __future__ import annotations

import pandas as pd
from sqlalchemy import text

from app_lib.db_v5 import engine


def _read_df(sql: str, params: dict | None = None) -> pd.DataFrame:
    """
    Executa uma consulta e retorna um DataFrame.
    """
    with engine.begin() as conn:
        return pd.read_sql(
            text(sql),
            conn,
            params=params or {},
        )


def get_fantasy_teams_df() -> pd.DataFrame:
    """
    Retorna os times no contrato já usado pela página Elencos:
    team_id, team_name.
    """
    return _read_df(
        """
        SELECT
            team_id,
            team_name
        FROM teams
        ORDER BY team_name
        """
    )


def get_fantasy_players_df() -> pd.DataFrame:
    """
    Retorna a base fantasy de jogadores, separada da tabela players
    utilizada pelo Leilão.

    source_player_id é devolvido como player_id para manter a
    compatibilidade com transforms.py, teams_page_context.py,
    transactions_ui.py e demais telas existentes.
    """
    return _read_df(
        """
        SELECT
            source_player_id AS player_id,
            player_name,
            nba_team,
            position,
            pts,
            trb,
            ast,
            stl,
            blk,
            three_p,
            tov,
            status,
            fantasy_value
        FROM fantasy_players
        ORDER BY player_name
        """
    )


def get_fantasy_roster_df() -> pd.DataFrame:
    """
    Retorna o elenco principal no mesmo formato da aba roster do Excel.
    """
    return _read_df(
        """
        SELECT
            team_id,
            source_player_id AS player_id,
            roster_order AS pos_order,
            roster_order AS "order",
            salarie_26_27,
            option_26_27,
            salarie_27_28,
            option_27_28,
            salarie_28_29,
            option_28_29,
            salarie_29_30,
            option_29_30
        FROM fantasy_roster
        ORDER BY team_id, roster_order NULLS LAST, source_player_id
        """
    )


def get_fantasy_development_df() -> pd.DataFrame:
    """
    Retorna o elenco Development no mesmo formato da aba development.
    """
    return _read_df(
        """
        SELECT
            team_id,
            source_player_id AS player_id,
            roster_order AS pos_order,
            roster_order AS "order",
            salarie_26_27,
            option_26_27,
            salarie_27_28,
            option_27_28,
            salarie_28_29,
            option_28_29,
            salarie_29_30,
            option_29_30
        FROM fantasy_development
        ORDER BY team_id, roster_order NULLS LAST, source_player_id
        """
    )


def get_fantasy_fines_df() -> pd.DataFrame:
    """
    Retorna multas no formato consumido por transforms.py.
    """
    return _read_df(
        """
        SELECT
            team_id,
            fine_26_27,
            fine_27_28,
            fine_28_29,
            fine_29_30,
            notes
        FROM fantasy_fines
        ORDER BY team_id
        """
    )


def get_fantasy_picks_df() -> pd.DataFrame:
    """
    Retorna picks no formato usado nas abas Elencos e Transactions.

    source_pick_id é exposto como pick_id.
    current_team_owner_id é a única fonte oficial de propriedade atual.
    """
    return _read_df(
        """
        SELECT
            source_pick_id AS pick_id,
            original_team_pick_id,
            round,
            year,
            current_team_owner_id
        FROM fantasy_picks
        ORDER BY
            current_team_owner_id,
            year,
            round,
            original_team_pick_id,
            source_pick_id
        """
    )


def get_fantasy_transactions_df() -> pd.DataFrame:
    """
    Retorna transactions no contrato esperado pela camada atual.
    """
    return _read_df(
        """
        SELECT
            source_transaction_id AS transaction_id,
            transaction_type,
            transaction_date,
            season,
            from_team_id,
            to_team_id,
            initiated_by,
            status,
            notes
        FROM fantasy_transactions
        ORDER BY
            transaction_date DESC NULLS LAST,
            source_transaction_id DESC
        """
    )


def get_fantasy_transaction_items_df() -> pd.DataFrame:
    """
    Retorna transaction items no contrato esperado pela camada atual.

    Para player: asset_id recebe player_source_id.
    Para pick: asset_id recebe pick_source_id.
    """
    return _read_df(
        """
        SELECT
            ft.source_transaction_id AS transaction_id,
            fti.source_item_id AS item_id,
            LOWER(fti.item_type) AS item_type,
            CASE
                WHEN LOWER(fti.item_type) = 'player'
                    THEN fti.player_source_id::TEXT
                WHEN LOWER(fti.item_type) = 'pick'
                    THEN fti.pick_source_id
                ELSE NULL
            END AS asset_id,
            fti.from_team_id,
            fti.to_team_id,
            fti.from_roster_type,
            fti.to_roster_type,
            fti.effective_season,
            fti.item_notes
        FROM fantasy_transaction_items fti
        JOIN fantasy_transactions ft
            ON ft.fantasy_transaction_id = fti.fantasy_transaction_id
        ORDER BY
            ft.source_transaction_id DESC,
            fti.fantasy_transaction_item_id
        """
    )


def get_fantasy_games_df() -> pd.DataFrame:
    """
    Já fica disponível para PNBC-05 — Classificação Neon.
    Não será usado pela página Elencos nesta subetapa.
    """
    return _read_df(
        """
        SELECT
            source_game_id AS id_jogo,
            team_1_id AS id_time_1,
            team_1_name AS nome_time_1,
            team_1_points AS pontos_time_1,
            team_2_points AS pontos_time_2,
            team_2_id AS id_time_2,
            team_2_name AS nome_time_2,
            round AS rodada
        FROM fantasy_games
        ORDER BY source_game_id
        """
    )


def get_fantasy_schedule_df() -> pd.DataFrame:
    """
    Já fica disponível para PNBC-06 — Calendário Neon.
    Mantém os nomes de coluna esperados pela aba Semana.
    """
    return _read_df(
        """
        SELECT
            week_number AS "SEMANANUM",
            week_start AS "SEMANAINICIO",
            nba_team_abbr AS "TEAMABBR",
            nba_team_name AS "TEAMNAME",
            game_number_in_week AS "JOGONASEMANA",
            game_date AS "GAMEDATE",
            nba_game_id AS "GAMEID",
            opponent_abbr AS "OPPONENTABBR",
            opponent_name AS "OPPONENTNAME",
            home_away AS "HOMEAWAY"
        FROM fantasy_schedule
        ORDER BY
            week_number,
            nba_team_abbr,
            game_number_in_week,
            game_date
        """
    )


def load_fantasy_data_from_neon() -> dict[str, pd.DataFrame]:
    """
    Carrega todas as tabelas necessárias no mesmo contrato de dados
    antes retornado por load_workbook_data('roster.xlsx').

    Nenhuma página precisa saber que os dados agora vêm do Neon:
    ela continua consumindo data['players'], data['roster'], etc.
    """
    return {
        "teams": get_fantasy_teams_df(),
        "players": get_fantasy_players_df(),
        "roster": get_fantasy_roster_df(),
        "development": get_fantasy_development_df(),
        "fines": get_fantasy_fines_df(),
        "picks": get_fantasy_picks_df(),
        "transactions": get_fantasy_transactions_df(),
        "transactionitems": get_fantasy_transaction_items_df(),
        "games": get_fantasy_games_df(),
        "Semana": get_fantasy_schedule_df(),
    }


def get_neon_data_counts() -> dict[str, int]:
    """
    Função de diagnóstico para comparar a carga Neon com o Excel.
    """
    data = load_fantasy_data_from_neon()

    return {
        name: int(len(df))
        for name, df in data.items()
    }