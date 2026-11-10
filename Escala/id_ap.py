import streamlit as st

import fantasy_gameid_backend as backend


st.set_page_config(
    page_title="Preencher GameID",
    page_icon="📅",
    layout="centered"
)

st.title("Preencher GameID por semana")
st.caption(
    "Preenche o GameID na planilha com base no calendário do Neon."
)

with st.form("formulario_gameid"):
    link = st.text_input(
        "Cole o link da planilha",
        placeholder="https://docs.google.com/spreadsheets/d/..."
    )

    semana = st.number_input(
        "Número da semana",
        min_value=1,
        max_value=30,
        step=1
    )

    jogo_semana = st.selectbox(
        "Jogo na semana",
        [1, 2, 3]
    )

    executar = st.form_submit_button("Preencher GameIDs")


if executar:
    if not link:
        st.error("Cole o link da planilha antes de executar.")
        st.stop()

    try:
        spreadsheet_id = backend.extrair_spreadsheet_id(link)

        with st.spinner("Buscando calendário e preenchendo planilha..."):
            resumo = backend.processar_planilha(
                spreadsheet_id,
                int(semana),
                int(jogo_semana)
            )

        st.success("Processamento concluído.")

        if resumo:
            st.dataframe(resumo, use_container_width=True)
        else:
            st.info("Nenhuma aba compatível foi encontrada.")

    except Exception as exc:
        st.error(f"Erro durante a execução: {exc}")