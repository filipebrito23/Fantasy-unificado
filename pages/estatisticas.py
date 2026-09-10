from __future__ import annotations

import pandas as pd
import streamlit as st

from app_lib.statistics_service import (
    EFFICIENCY_FORMULA_LABEL,
    get_player_consistency,
    get_player_consistency_history,
    get_player_consistency_scatter,
    get_player_game_log,
    get_player_statistics,
    get_statistics_teams,
    get_team_consistency,
    get_team_consistency_history,
    get_team_consistency_scatter,
    get_team_game_log,
    get_team_statistics,
)

st.set_page_config(page_title="Estatísticas", layout="wide")

METRIC_LABELS = {
    "pts": "PTS",
    "reb": "REB",
    "ast": "AST",
    "stl": "STL",
    "blk": "BLK",
    "three_pt": "3PT",
    "turnovers": "TO",
    "efficiency": "Eficiência",
}


def _format_currency(value) -> str:
    if value is None or pd.isna(value):
        return "—"
    return (
        f"R$ {float(value):,.0f}"
        .replace(",", "X")
        .replace(".", ",")
        .replace("X", ".")
    )


def _format_number(value, digits: int = 2) -> str:
    if value is None or pd.isna(value):
        return "—"
    return f"{float(value):,.{digits}f}".replace(".", ",")


def _safe_metric(label: str, value, digits: int = 2) -> None:
    st.metric(label, _format_number(value, digits))


def _player_table(df: pd.DataFrame) -> pd.DataFrame:
    cols = [
        "player_name",
        "team_name",
        "position",
        "games_played",
        "avg_pts",
        "avg_reb",
        "avg_ast",
        "avg_stl",
        "avg_blk",
        "avg_three_pt",
        "avg_turnovers",
        "avg_efficiency",
        "avg_pts_last_4",
        "avg_pts_last_8",
        "avg_pts_last_12",
        "efficiency_per_million",
    ]
    out = df[[col for col in cols if col in df.columns]].copy()
    return out.rename(
        columns={
            "player_name": "Jogador",
            "team_name": "Time",
            "position": "Posição",
            "games_played": "Jogos",
            "avg_pts": "PTS",
            "avg_reb": "REB",
            "avg_ast": "AST",
            "avg_stl": "STL",
            "avg_blk": "BLK",
            "avg_three_pt": "3PT",
            "avg_turnovers": "TO",
            "avg_efficiency": "Eficiência",
            "avg_pts_last_4": "PTS últ. 4",
            "avg_pts_last_8": "PTS últ. 8",
            "avg_pts_last_12": "PTS últ. 12",
            "efficiency_per_million": "Eficiência / R$ 1 mi",
        }
    )


def _team_table(df: pd.DataFrame) -> pd.DataFrame:
    cols = [
        "team_name",
        "games_with_stats",
        "avg_pts",
        "avg_reb",
        "avg_ast",
        "avg_stl",
        "avg_blk",
        "avg_three_pt",
        "avg_turnovers",
        "avg_efficiency",
        "stddev_pts",
    ]
    out = df[[col for col in cols if col in df.columns]].copy()
    return out.rename(
        columns={
            "team_name": "Time",
            "games_with_stats": "Jogos",
            "avg_pts": "PTS méd.",
            "avg_reb": "REB méd.",
            "avg_ast": "AST méd.",
            "avg_stl": "STL méd.",
            "avg_blk": "BLK méd.",
            "avg_three_pt": "3PT méd.",
            "avg_turnovers": "TO méd.",
            "avg_efficiency": "Eficiência méd.",
            "stddev_pts": "Desvio-padrão de PTS",
        }
    )


def _consistency_player_table(df: pd.DataFrame) -> pd.DataFrame:
    cols = [
        "player_name",
        "team_name",
        "games_played",
        "avg_pts",
        "stddev_pts",
        "avg_reb",
        "stddev_reb",
        "avg_ast",
        "stddev_ast",
        "avg_stl",
        "stddev_stl",
        "avg_blk",
        "stddev_blk",
        "avg_three_pt",
        "stddev_three_pt",
        "avg_turnovers",
        "stddev_turnovers",
        "avg_efficiency",
        "stddev_efficiency",
    ]
    out = df[[col for col in cols if col in df.columns]].copy()
    return out.rename(
        columns={
            "player_name": "Jogador",
            "team_name": "Time",
            "games_played": "Jogos",
            "avg_pts": "PTS méd.",
            "stddev_pts": "DP PTS",
            "avg_reb": "REB méd.",
            "stddev_reb": "DP REB",
            "avg_ast": "AST méd.",
            "stddev_ast": "DP AST",
            "avg_stl": "STL méd.",
            "stddev_stl": "DP STL",
            "avg_blk": "BLK méd.",
            "stddev_blk": "DP BLK",
            "avg_three_pt": "3PT méd.",
            "stddev_three_pt": "DP 3PT",
            "avg_turnovers": "TO méd.",
            "stddev_turnovers": "DP TO",
            "avg_efficiency": "Eficiência méd.",
            "stddev_efficiency": "DP Eficiência",
        }
    )


def _consistency_team_table(df: pd.DataFrame) -> pd.DataFrame:
    cols = [
        "team_name",
        "games_with_stats",
        "avg_pts",
        "stddev_pts",
        "avg_reb",
        "stddev_reb",
        "avg_ast",
        "stddev_ast",
        "avg_stl",
        "stddev_stl",
        "avg_blk",
        "stddev_blk",
        "avg_three_pt",
        "stddev_three_pt",
        "avg_turnovers",
        "stddev_turnovers",
        "avg_efficiency",
        "stddev_efficiency",
    ]
    out = df[[col for col in cols if col in df.columns]].copy()
    return out.rename(
        columns={
            "team_name": "Time",
            "games_with_stats": "Jogos",
            "avg_pts": "PTS méd.",
            "stddev_pts": "DP PTS",
            "avg_reb": "REB méd.",
            "stddev_reb": "DP REB",
            "avg_ast": "AST méd.",
            "stddev_ast": "DP AST",
            "avg_stl": "STL méd.",
            "stddev_stl": "DP STL",
            "avg_blk": "BLK méd.",
            "stddev_blk": "DP BLK",
            "avg_three_pt": "3PT méd.",
            "stddev_three_pt": "DP 3PT",
            "avg_turnovers": "TO méd.",
            "stddev_turnovers": "DP TO",
            "avg_efficiency": "Eficiência méd.",
            "stddev_efficiency": "DP Eficiência",
        }
    )


def render_players_tab(teams_df: pd.DataFrame) -> None:
    st.subheader("Estatísticas dos jogadores")
    st.caption(
        "Médias calculadas apenas com jogos que possuem estatísticas importadas."
    )

    team_options = {"Todos os times": None}
    for row in teams_df.itertuples(index=False):
        team_options[row.team_name] = int(row.team_id)

    col_filter_1, col_filter_2 = st.columns([1, 2])

    with col_filter_1:
        selected_team_name = st.selectbox(
            "Time",
            list(team_options.keys()),
            key="stats_player_team",
        )
        selected_team_id = team_options[selected_team_name]
        players_df = get_player_statistics(selected_team_id)

        if players_df.empty:
            st.info(
                "Ainda não existem estatísticas de jogadores importadas para este filtro."
            )
            return

    with col_filter_2:
        player_names = ["Todos os jogadores"] + players_df["player_name"].tolist()
        selected_player_name = st.selectbox(
            "Jogador",
            player_names,
            key="stats_player_name",
        )

    filtered_df = players_df.copy()
    if selected_player_name != "Todos os jogadores":
        filtered_df = filtered_df[
            filtered_df["player_name"] == selected_player_name
        ].copy()

    if filtered_df.empty:
        st.info("Nenhum jogador encontrado para o filtro selecionado.")
        return

    if selected_player_name == "Todos os jogadores":
        total_games = int(filtered_df["games_played"].sum())

        c1, c2, c3, c4 = st.columns(4)

        with c1:
            _safe_metric("Jogadores com estatísticas", len(filtered_df), 0)

        with c2:
            _safe_metric("Registros de jogos", total_games, 0)

        with c3:
            _safe_metric("PTS médios da liga", filtered_df["avg_pts"].mean())

        with c4:
            _safe_metric(
                "Eficiência média da liga",
                filtered_df["avg_efficiency"].mean(),
            )

        st.markdown("#### Tabela completa de médias")

        st.dataframe(
            _player_table(
                filtered_df.sort_values(
                    ["avg_efficiency", "avg_pts", "player_name"],
                    ascending=[False, False, True],
                    na_position="last",
                )
            ),
            use_container_width=True,
            hide_index=True,
        )

    else:
        player = filtered_df.iloc[0]

        st.markdown(f"#### {player['player_name']} — {player['team_name']}")
        st.caption(
            f"Posição: {player['position'] or '—'} · "
            f"Rodadas registradas: {player['first_round']} a {player['last_round']}"
        )

        # Todo o bloco atual de detalhes do jogador deve ficar aqui:
        # cards, médias por categoria, histórico e consistência.

    player = filtered_df.iloc[0]
    st.markdown(f"#### {player['player_name']} — {player['team_name']}")
    st.caption(
        f"Posição: {player['position'] or '—'} · "
        f"Rodadas registradas: {player['first_round']} a {player['last_round']}"
    )

    c1, c2, c3, c4, c5 = st.columns(5)
    with c1:
        _safe_metric("Jogos", player["games_played"], 0)
    with c2:
        _safe_metric("PTS médios", player["avg_pts"])
    with c3:
        _safe_metric("Eficiência média", player["avg_efficiency"])
    with c4:
        _safe_metric("PTS últimas 4", player["avg_pts_last_4"])
    with c5:
        _safe_metric(
            "Eficiência / R$ 1 mi",
            player["efficiency_per_million"],
            4,
        )

    c1, c2, c3, c4 = st.columns(4)
    with c1:
        _safe_metric("PTS últimas 8", player["avg_pts_last_8"])
    with c2:
        _safe_metric("PTS últimas 12", player["avg_pts_last_12"])
    with c3:
        st.metric(
            "Salário 2026–27",
            _format_currency(player["current_salary"]),
        )
    with c4:
        _safe_metric("Eficiência total", player["total_efficiency"])
        
    st.markdown("#### Médias por categoria")
    averages = pd.DataFrame(
        {
            "PTS": [player["avg_pts"]],
            "REB": [player["avg_reb"]],
            "AST": [player["avg_ast"]],
            "STL": [player["avg_stl"]],
            "BLK": [player["avg_blk"]],
            "3PT": [player["avg_three_pt"]],
            "TO": [player["avg_turnovers"]],
            "Eficiência": [player["avg_efficiency"]],
        }
    ).T.rename(columns={0:"Média"})
    
    st.dataframe(averages, use_container_width=True, hide_index=True)

    st.divider()
    st.subheader("Histórico por rodada")

    game_log = get_player_game_log(
        int(player["source_player_id"]),
        int(player["team_id"]),
    )
    if game_log.empty:
        st.info("Não há partidas registradas para este jogador.")
    else:
        metric = st.selectbox(
            "Métrica",
            list(METRIC_LABELS.keys()),
            format_func=lambda value: METRIC_LABELS[value],
            key="player_history_metric",
        )
        st.caption(
            f"Evolução de {METRIC_LABELS[metric]} do jogador nas rodadas importadas."
        )

        # Preparar dados: garantir round inteiro e único por rodada
        plot_df = game_log.copy()
        plot_df["round"] = pd.to_numeric(plot_df["round"], errors="coerce").astype("Int64")
        plot_df[metric] = pd.to_numeric(plot_df[metric], errors="coerce")
        plot_df = plot_df.dropna(subset=["round", metric])
        plot_df = plot_df.sort_values("round").groupby("round").first().reset_index()
        plot_df = plot_df.set_index("round")[[metric]]

        st.line_chart(plot_df, width="stretch")
        st.dataframe(game_log, use_container_width=True, hide_index=True)

    st.divider()
    st.subheader("Consistência do jogador")
    st.caption(
        "Desvio-padrão amostral mede a variabilidade do desempenho entre jogos. "
        "Quanto menor o valor, mais consistente é o jogador naquela métrica."
    )

    metric = st.selectbox(
        "Métrica",
        list(METRIC_LABELS.keys()),
        format_func=lambda value: METRIC_LABELS[value],
        key="player_consistency_metric",
    )

    history = get_player_consistency_history(
        int(player["source_player_id"]),
        int(player["team_id"]),
        metric=metric,
    )
    if not history.empty:
        # Preparar dados
        plot_df = history.copy()
        plot_df["round"] = pd.to_numeric(plot_df["round"], errors="coerce").astype("Int64")
        for col in ["value", "running_avg", "lower_bound", "upper_bound"]:
            plot_df[col] = pd.to_numeric(plot_df[col], errors="coerce")
        plot_df = plot_df.dropna(subset=["round", "value", "running_avg"])
        plot_df = plot_df.sort_values("round").groupby("round").first().reset_index()
        plot_df = plot_df.set_index("round")[["value", "running_avg", "lower_bound", "upper_bound"]]

        st.line_chart(plot_df, width="stretch")

        st.dataframe(
            history.rename(
                columns={
                    "round": "Rodada",
                    "value": "Valor",
                    "running_avg": "Média acumulada",
                    "running_stddev": "DP acumulado",
                    "lower_bound": "Limite inferior",
                    "upper_bound": "Limite superior",
                }
            ),
            use_container_width=True,
            hide_index=True,
        )


def render_teams_tab(teams_df: pd.DataFrame) -> None:
    st.subheader("Estatísticas dos times")
    st.caption(
        "Médias e totais calculados apenas a partir de confrontos "
        "com estatísticas importadas."
    )

    team_stats_df = get_team_statistics()
    if team_stats_df.empty:
        st.info("Ainda não existem confrontos completos com estatísticas importadas.")
        return

    total_matchups = int(team_stats_df["games_with_stats"].sum() / 2)
    c1, c2, c3, c4 = st.columns(4)
    with c1:
        _safe_metric("Times com dados", len(team_stats_df), 0)
    with c2:
        _safe_metric("Confrontos analisados", total_matchups, 0)
    with c3:
        _safe_metric("PTS médios da liga", team_stats_df["avg_pts"].mean())
    with c4:
        _safe_metric(
            "Eficiência média da liga",
            team_stats_df["avg_efficiency"].mean(),
        )

    st.markdown("#### Médias por confronto")
    st.dataframe(
        _team_table(
            team_stats_df.sort_values(
                ["avg_efficiency", "avg_pts", "team_name"],
                ascending=[False, False, True],
                na_position="last",
            )
        ),
        use_container_width=True,
        hide_index=True,
    )

    st.markdown("#### Totais acumulados por categoria")
    totals_cols = [
        "team_name",
        "games_with_stats",
        "total_pts",
        "total_reb",
        "total_ast",
        "total_stl",
        "total_blk",
        "total_three_pt",
        "total_turnovers",
        "total_efficiency",
    ]
    totals_df = team_stats_df[
        [col for col in totals_cols if col in team_stats_df.columns]
    ].copy()
    totals_df = totals_df.rename(
        columns={
            "team_name": "Time",
            "games_with_stats": "Jogos",
            "total_pts": "PTS total",
            "total_reb": "REB total",
            "total_ast": "AST total",
            "total_stl": "STL total",
            "total_blk": "BLK total",
            "total_three_pt": "3PT total",
            "total_turnovers": "TO total",
            "total_efficiency": "Eficiência total",
        }
    )
    st.dataframe(
        totals_df.sort_values(
            ["Eficiência total", "PTS total", "Time"],
            ascending=[False, False, True],
            na_position="last",
        ),
        use_container_width=True,
        hide_index=True,
    )

    available_team_ids = set(team_stats_df["team_id"])
    team_options = {
        row.team_name: int(row.team_id)
        for row in teams_df.itertuples(index=False)
        if int(row.team_id) in available_team_ids
    }
    if not team_options:
        return

    selected_team_name = st.selectbox(
        "Detalhar time",
        list(team_options.keys()),
        key="stats_team_detail",
    )
    selected_team_id = team_options[selected_team_name]
    selected_team = team_stats_df[
        team_stats_df["team_id"] == selected_team_id
    ].iloc[0]

    st.markdown(f"#### Histórico: {selected_team_name}")
    c1, c2, c3, c4 = st.columns(4)
    with c1:
        _safe_metric("Jogos com estatísticas", selected_team["games_with_stats"], 0)
    with c2:
        _safe_metric("PTS médios", selected_team["avg_pts"])
    with c3:
        _safe_metric("Eficiência média", selected_team["avg_efficiency"])
    with c4:
        _safe_metric("Desvio-padrão de PTS", selected_team["stddev_pts"])

    st.divider()
    st.subheader("Histórico por rodada")

    game_log = get_team_game_log(selected_team_id)
    if game_log.empty:
        st.info("Não há confrontos completos registrados para este time.")
    else:
        metric = st.selectbox(
            "Métrica",
            list(METRIC_LABELS.keys()),
            format_func=lambda value: METRIC_LABELS[value],
            key="team_history_metric",
        )
        st.caption(
            f"Evolução de {METRIC_LABELS[metric]} do time nas rodadas importadas."
        )
        st.line_chart(
            game_log.set_index("round")[[metric]],
            use_container_width=True,
        )
        st.dataframe(game_log, use_container_width=True, hide_index=True)

    st.divider()
    st.subheader("Consistência do time")
    st.caption(
        "Desvio-padrão amostral mede a variabilidade do desempenho entre jogos. "
        "Quanto menor o valor, mais consistente é o time naquela métrica."
    )

    metric = st.selectbox(
        "Métrica",
        list(METRIC_LABELS.keys()),
        format_func=lambda value: METRIC_LABELS[value],
        key="team_consistency_metric",
    )

    history = get_team_consistency_history(selected_team_id, metric=metric)
    if not history.empty:
        chart_df = history.set_index("round")[
            ["value", "running_avg", "lower_bound", "upper_bound"]
        ]
        st.line_chart(chart_df, use_container_width=True)
        st.dataframe(
            history.rename(
                columns={
                    "round": "Rodada",
                    "value": "Valor",
                    "running_avg": "Média acumulada",
                    "running_stddev": "DP acumulado",
                    "lower_bound": "Limite inferior",
                    "upper_bound": "Limite superior",
                }
            ),
            use_container_width=True,
            hide_index=True,
        )


def render_consistency_tab() -> None:
    st.subheader("Consistência")
    st.caption(
        "Desvio-padrão amostral para PTS, REB, AST, STL, BLK, 3PT, TO e eficiência. "
        "Valores menores indicam maior regularidade."
    )

    tab_players, tab_teams = st.tabs(["Jogadores", "Times"])

    with tab_players:
        st.markdown("#### Tabela de consistência dos jogadores")
        consistency_df = get_player_consistency(min_games=2)
        if consistency_df.empty:
            st.info("Dados insuficientes para calcular a consistência dos jogadores.")
        else:
            st.dataframe(
                _consistency_player_table(
                    consistency_df.sort_values(
                        ["avg_efficiency", "avg_pts", "player_name"],
                        ascending=[False, False, True],
                        na_position="last",
                    )
                ),
                use_container_width=True,
                hide_index=True,
            )

        st.divider()
        st.markdown("#### Dispersão: média × consistência (jogadores)")
        metric = st.selectbox(
            "Métrica",
            list(METRIC_LABELS.keys()),
            format_func=lambda value: METRIC_LABELS[value],
            key="player_scatter_metric",
        )
        min_games = st.slider(
            "Mínimo de jogos",
            min_value=2,
            max_value=10,
            value=4,
            key="player_scatter_min_games",
        )
        scatter = get_player_consistency_scatter(
            min_games=min_games,
            metric=metric,
        )
        if scatter.empty:
            st.info("Dados insuficientes para o gráfico de dispersão.")
        else:
            st.scatter_chart(
                scatter.set_index("player_name")[["avg_value", "stddev_value"]],
                x_label="Média",
                y_label="Desvio-padrão",
                use_container_width=True,
            )
            st.caption(
                "Cada ponto representa um jogador com pelo menos "
                f"{min_games} jogos. Eixo X: média da métrica; "
                "eixo Y: desvio-padrão."
            )

    with tab_teams:
        st.markdown("#### Tabela de consistência dos times")
        consistency_df = get_team_consistency(min_games=2)
        if consistency_df.empty:
            st.info("Dados insuficientes para calcular a consistência dos times.")
        else:
            st.dataframe(
                _consistency_team_table(
                    consistency_df.sort_values(
                        ["avg_efficiency", "avg_pts", "team_name"],
                        ascending=[False, False, True],
                        na_position="last",
                    )
                ),
                use_container_width=True,
                hide_index=True,
            )

        st.divider()
        st.markdown("#### Dispersão: média × consistência (times)")
        metric = st.selectbox(
            "Métrica",
            list(METRIC_LABELS.keys()),
            format_func=lambda value: METRIC_LABELS[value],
            key="team_scatter_metric",
        )
        min_games = st.slider(
            "Mínimo de jogos",
            min_value=2,
            max_value=10,
            value=3,
            key="team_scatter_min_games",
        )
        scatter = get_team_consistency_scatter(
            min_games=min_games,
            metric=metric,
        )
        if scatter.empty:
            st.info("Dados insuficientes para o gráfico de dispersão.")
        else:
            st.scatter_chart(
                scatter.set_index("team_name")[["avg_value", "stddev_value"]],
                x_label="Média",
                y_label="Desvio-padrão",
                use_container_width=True,
            )
            st.caption(
                "Cada ponto representa um time com pelo menos "
                f"{min_games} jogos. Eixo X: média da métrica; "
                "eixo Y: desvio-padrão."
            )


def main() -> None:
    st.title("Estatísticas")
    st.caption("Estatísticas avançadas de jogadores e times")

    teams_df = get_statistics_teams()
    if teams_df.empty:
        st.error("Nenhum time foi encontrado no banco de dados.")
        st.stop()

    tab_players, tab_teams, tab_consistency = st.tabs(
        ["Jogadores", "Times", "Consistência"]
    )

    with tab_players:
        render_players_tab(teams_df)

    with tab_teams:
        render_teams_tab(teams_df)

    with tab_consistency:
        render_consistency_tab()


if __name__ == "__main__":
    main()
