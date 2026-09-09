from __future__ import annotations

import streamlit as st

from app_lib.ratings_service import (
    get_available_rounds,
    get_player_options,
    get_player_rating_history,
    get_player_ratings_by_round,
    get_player_round_laggards,
    get_player_round_leaders,
    get_player_season_ranking,
    get_round_mvps,
    get_round_summary_stats,
    get_team_options,
    get_team_rating_history,
    get_team_ratings_by_round,
    get_team_round_laggards,
    get_team_round_leaders,
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
        "em seguida, recalculate_ratings.sql após importar as estatistics."
    )
    st.stop()

latest_round = max(rounds)


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
        st.info(" Não há ratings individuais disponíveis.")
    else:
        top_player = player_ranking.iloc[0]
        st.metric(
            label="Líder de rating (temporada)",
            value=top_player["jogador"],
            delta=f"Rating médio {top_player['rating_medio']:.2f}",
        )

        top_n = st.selectbox(
            "Mostrar",
            options=[10, 20, 50, 100],
            index=0,
            key="players_top_n",
            label_visibility="collapsed",
        )
        ranking_display = player_ranking.head(top_n)

        st.dataframe(
            _format_table(ranking_display),
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

        st.subheader("Destaques da rodada")

        selected_round_players = st.selectbox(
            "Rodada",
            rounds,
            format_func=lambda value: f"Rodada {value}",
            key="ratings_player_round_highlights",
        )

        leaders = get_player_round_leaders(selected_round_players)
        laggards = get_player_round_laggards(selected_round_players)

        if not leaders.empty:
            st.markdown("### 3 melhores da rodada")
            cols = st.columns(3)
            for i, row in leaders.iterrows():
                with cols[i]:
                    st.metric(
                        label=f"{i+1}º - {row['jogador']} ({row['time']})",
                        value=f"Rating {row['rating']:.2f}",
                        delta=f"Ef {row['eficiencia']:.2f} | PTS {row['pts']}",
                    )

        if not laggards.empty:
            st.markdown("### 3 piores da rodada")
            cols = st.columns(3)
            for i, row in laggards.iterrows():
                with cols[i]:
                    st.metric(
                        label=f"{i+1}º - {row['jogador']} ({row['time']})",
                        value=f"Rating {row['rating']:.2f}",
                        delta=f"Ef {row['eficiencia']:.2f} | PTS {row['pts']}",
                    )

        st.divider()

        st.subheader("Ratings por rodada")

        player_round = st.selectbox(
            "Rodada",
            rounds,
            format_func=lambda value: f"Rodada {value}",
            key="ratings_player_round_table",
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
                    "eficiencia": st.column_config.NumberColumn("EficiÃªncia", format="%.2f"),
                    "pts": "PTS",
                    "reb": "REB",
                    "ast": "AST",
                    "stl": "STL",
                    "blk": "BLK",
                    "three_pt": "3PT",
                    "turnovers": "TO",
                },
            )

        st.divider()

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
            st.line_chart(
                player_history.set_index("rodada")[["rating"]],
                use_container_width=True,
            )

        st.divider()



with tab_teams:
    st.subheader("Ranking da temporada")

    team_ranking = get_team_season_ranking()
    if team_ranking.empty:
        st.info("NÃ£o hÃ¡ ratings de times disponÃ¬veis.")
    else:
        top_team = team_ranking.iloc[0]
        st.metric(
            label="Líder de rating (temporada)",
            value=top_team["time"],
            delta=f"Rating médio {top_team['rating_medio']:.2f}",
        )

        top_n = st.selectbox(
            "Mostrar",
            options=[10, 20, 50, 100],
            index=0,
            key="teams_top_n",
            label_visibility="collapsed",
        )
        ranking_display = team_ranking.head(top_n)

        st.dataframe(
            _format_table(ranking_display),
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

        st.subheader("Destaques da rodada")

        selected_round_teams = st.selectbox(
            "Rodada",
            rounds,
            format_func=lambda value: f"Rodada {value}",
            key="ratings_team_round_highlights",
        )

        team_leaders = get_team_round_leaders(selected_round_teams)
        team_laggards = get_team_round_laggards(selected_round_teams)

        if not team_leaders.empty:
            st.markdown("### 3 melhores times da rodada")
            cols = st.columns(3)
            for i, row in team_leaders.iterrows():
                with cols[i]:
                    st.metric(
                        label=f"{i+1}º - {row['time']}",
                        value=f"Rating {row['rating']:.2f}",
                        delta=f"Ef {row['eficiencia_time']:.2f}",
                    )

        if not team_laggards.empty:
            st.markdown("### 3 piores times da rodada")
            cols = st.columns(3)
            for i, row in team_laggards.iterrows():
                with cols[i]:
                    st.metric(
                        label=f"{i+1}º - {row['time']}",
                        value=f"Rating {row['rating']:.2f}",
                        delta=f"Ef {row['eficiencia_time']:.2f}",
                    )

        st.divider()

        st.subheader("Ratings por rodada")

        team_round = st.selectbox(
            "Rodada",
            rounds,
            format_func=lambda value: f"Rodada {value}",
            key="ratings_team_round_table",
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
                    "eficiencia_time": st.column_config.NumberColumn("Eficência do time", format="%.2f"),
                    "media_liga": st.column_config.NumberColumn("Média da liga", format="%.2f"),
                },
            )

        st.divider()

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
            st.line_chart(
                team_history.set_index("rodada")[["rating"]],
                use_container_width=True,
            )

        st.divider()



with tab_mvps:
    st.subheader("MVPs da rodada")
    st.caption(
        "Desempates: maior eficiência, mais pontos, menos turnovers e nome em ordem alfabética."
    )
    mvps = get_round_mvps()
    if mvps.empty:
        st.info("Ainda nÃ£o hÃ¡ MVPs calculados.")
    else:
        latest = mvps.iloc[0]
        st.metric(
            label=f"MVP da Rodada {int(latest['rodada'])}",
            value=latest["jogador"],
            delta=f"Rating {latest['rating']:.2f} | Eficiência {latest['eficiencia']:.2f}",
        )

        col1, col2, col3, col4 = st.columns(4)
        with col1:
            st.metric("PTS", int(latest["pts"]))
        with col2:
            st.metric("REB", int(latest["reb"]))
        with col3:
            st.metric("AST", int(latest["ast"]))
        with col4:
            st.metric("3PT", int(latest["three_pt"]))

        st.divider()

        st.dataframe(
            mvps.style.format(
                {
                    "rating": "{:.2f}",
                    "eficiencia": "{:.2f}",
                },
                na_rep="â§»",
            ),
            use_container_width=True,
            hide_index=True,
            column_config={
                "rodada": "Rodada",
                "jogador": "Jogador",
                "time": "Time",
                "rating": st.column_config.NumberColumn("Rating", format="%.2f"),
                "eficiencia": st.column_config.NumberColumn("EficiÃªncia", format="%.2f"),
                "pts": "PTS",
                "reb": "REB",
                "ast": "AST",
                "stl": "STL",
                "blk": "BLK",
                "three_pt": "3PT",
                "turnovers": "TO",
            },
        )