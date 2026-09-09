from __future__ import annotations

import streamlit as st

from app_lib.ratings_service import (
    get_available_rounds,
    get_player_options,
    get_player_rating_history,
    get_player_ratings_by_round,
    get_player_season_ranking,
    get_round_mvps,
    get_team_options,
    get_team_rating_history,
    get_team_ratings_by_round,
    get_team_season_ranking,
)

st.title("Ratings")
st.caption(
    "Rating 10 representa a média da rodada. Valores acima de 10 indicam "
    "desempenho acima da média; valores abaixo de 10 indicam desempenho abaixo dela."
)

rounds = get_available_rounds()
if not rounds:
    st.info(
        "Ainda não há ratings calculados. Execute recalculate_efficiency.sql e, "
        "em seguida, recalculate_ratings.sql após importar as estatísticas."
    )
    st.stop()


def _format_table(df):
    return df.style.format(
        {
            "rating_medio": "{:.2f}",
            "melhor_rating": "{:.2f}",
            "eficiencia_media": "{:.2f}",
            "rating": "{:.2f}",
            "eficiencia": "{:.2f}",
            "eficiencia_time": "{:.2f}",
            "media_liga": "{:.2f}",
        },
        na_rep="—",
    )


tab_players, tab_teams, tab_mvps = st.tabs(["Jogadores", "Times", "MVPs"])

with tab_players:
    st.subheader("Ranking da temporada")
    player_ranking = get_player_season_ranking()
    if player_ranking.empty:
        st.info("Não há ratings individuais disponíveis.")
    else:
        st.dataframe(
            _format_table(player_ranking),
            use_container_width=True,
            hide_index=True,
            column_config={
                "jogador": "Jogador",
                "time": "Time",
                "jogos": st.column_config.NumberColumn("Jogos", format="%d"),
                "rating_medio": st.column_config.NumberColumn("Rating médio", format="%.2f"),
                "eficiencia_media": st.column_config.NumberColumn("Eficiência média", format="%.2f"),
                "melhor_rating": st.column_config.NumberColumn("Melhor rating", format="%.2f"),
            },
        )

        st.subheader("Evolução de rating")
        player_options = get_player_options()
        selected_player_name = st.selectbox(
            "Jogador",
            player_options["jogador"].tolist(),
            key="ratings_player_selector",
        )
        selected_player_id = int(
            player_options.loc[
                player_options["jogador"] == selected_player_name,
                "source_player_id",
            ].iloc[0]
        )
        player_history = get_player_rating_history(selected_player_id)
        if not player_history.empty:
            st.line_chart(player_history.set_index("rodada")[["rating"]], use_container_width=True)

    st.subheader("Ratings por rodada")
    player_round = st.selectbox(
        "Rodada",
        rounds,
        format_func=lambda value: f"Rodada {value}",
        key="ratings_player_round",
    )
    player_round_df = get_player_ratings_by_round(player_round)
    if not player_round_df.empty:
        st.dataframe(
            _format_table(player_round_df),
            use_container_width=True,
            hide_index=True,
            column_config={
                "rodada": "Rodada",
                "jogador": "Jogador",
                "time": "Time",
                "rating": st.column_config.NumberColumn("Rating", format="%.2f"),
                "eficiencia": st.column_config.NumberColumn("Eficiência", format="%.2f"),
                "pts": "PTS",
                "reb": "REB",
                "ast": "AST",
                "stl": "STL",
                "blk": "BLK",
                "three_pt": "3PT",
                "turnovers": "TO",
            },
        )

with tab_teams:
    st.subheader("Ranking da temporada")
    team_ranking = get_team_season_ranking()
    if team_ranking.empty:
        st.info("Não há ratings de times disponíveis.")
    else:
        st.dataframe(
            _format_table(team_ranking),
            use_container_width=True,
            hide_index=True,
            column_config={
                "time": "Time",
                "jogos": st.column_config.NumberColumn("Jogos", format="%d"),
                "rating_medio": st.column_config.NumberColumn("Rating médio", format="%.2f"),
                "eficiencia_media": st.column_config.NumberColumn("Eficiência média", format="%.2f"),
                "melhor_rating": st.column_config.NumberColumn("Melhor rating", format="%.2f"),
            },
        )

        st.subheader("Evolução de rating")
        team_options = get_team_options()
        selected_team_name = st.selectbox(
            "Time",
            team_options["time"].tolist(),
            key="ratings_team_selector",
        )
        selected_team_id = int(
            team_options.loc[team_options["time"] == selected_team_name, "team_id"].iloc[0]
        )
        team_history = get_team_rating_history(selected_team_id)
        if not team_history.empty:
            st.line_chart(team_history.set_index("rodada")[["rating"]], use_container_width=True)

    st.subheader("Ratings por rodada")
    team_round = st.selectbox(
        "Rodada",
        rounds,
        format_func=lambda value: f"Rodada {value}",
        key="ratings_team_round",
    )
    team_round_df = get_team_ratings_by_round(team_round)
    if not team_round_df.empty:
        st.dataframe(
            _format_table(team_round_df),
            use_container_width=True,
            hide_index=True,
            column_config={
                "rodada": "Rodada",
                "time": "Time",
                "rating": st.column_config.NumberColumn("Rating", format="%.2f"),
                "eficiencia_time": st.column_config.NumberColumn("Eficiência do time", format="%.2f"),
                "media_liga": st.column_config.NumberColumn("Média da liga", format="%.2f"),
            },
        )

with tab_mvps:
    st.subheader("MVPs da rodada")
    st.caption(
        "Desempates: maior eficiência, mais pontos, menos turnovers e nome em ordem alfabética."
    )
    mvps = get_round_mvps()
    if mvps.empty:
        st.info("Ainda não há MVPs calculados.")
    else:
        latest_mvp = mvps.iloc[0]
        left, middle, right = st.columns(3)
        left.metric("MVP mais recente", latest_mvp["jogador"])
        middle.metric("Rating", f"{latest_mvp['rating']:.2f}")
        right.metric("Eficiência", f"{latest_mvp['eficiencia']:.2f}")

        st.dataframe(
            _format_table(mvps),
            use_container_width=True,
            hide_index=True,
            column_config={
                "rodada": "Rodada",
                "jogador": "Jogador",
                "time": "Time",
                "rating": st.column_config.NumberColumn("Rating", format="%.2f"),
                "eficiencia": st.column_config.NumberColumn("Eficiência", format="%.2f"),
                "pts": "PTS",
                "reb": "REB",
                "ast": "AST",
                "stl": "STL",
                "blk": "BLK",
                "three_pt": "3PT",
                "turnovers": "TO",
            },
        )