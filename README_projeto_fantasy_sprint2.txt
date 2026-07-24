Arquivo resumido para controle dos módulos em uso na Sprint 2. A ideia é manter este documento sempre
atualizado quando algum arquivo for criado, alterado ou passar a ter nova responsabilidade.

Sprint 2 — foco principal

- Consolidar a página teams.py como compositora de contexto + abas.
- Extrair a aba de transactions para módulos próprios de UI e helpers de formulário.
- Manter o comportamento já validado de roster, picks e histórico.

Arquivos principais

uni.py — Shell principal da aplicação; configura Streamlit, executa startup, controla login/logout,
         troca obrigatória de senha e abre as páginas integradas.[file:679][file:685][file:688]
home.py — Página Home da liga; exibe abas como regras, calendário, draft, mural, links, posts e
          comentários.[file:681][file:689]
teams.py — Página de elencos e transactions; após a Sprint 2 atua como compositor de contexto e
           delega a renderização das abas para módulos especializados.[file:683][file:697]
lei.py — Página do leilão integrada ao shell principal; usa a base de bids e estados dos
         jogadores.[file:682][file:687]
classificacao.py — Página de classificação integrada ao shell principal.[file:680]

db_v5.py — Camada de banco; monta conexão PostgreSQL/SQLite, faz healthcheck e cria a estrutura
           principal das tabelas da aplicação.[file:688]
auth_v5.py — Serviço de autenticação; faz hash e validação de senha, login, troca de senha e leitura
             de usuários.[file:685]
permissions.py — Regras de permissão; concentra verificações de admin para páginas e ações
                 restritas.[file:690]
home_service.py — Serviço da Home; consulta e grava abas, posts, comentários, calendário, links e
                  draft board no banco.[file:689]
auction_v5.py — Serviço do leilão; controla bids, expiração, auditoria e validações de cap para
                propostas.[file:687]
transactions_service.py — Serviço de transactions; grava transactions, valida itens, atualiza rosters
                           e monta histórico a partir do Excel/base usada por elencos.[file:693]
transforms.py — Regras de transformação para exibição; monta visões de roster, picks, totais e
                resumos por temporada/posição.[file:694][file:697]

Helpers e serviços centrais da Sprint 2

teams_page_context.py — Helper de contexto de teams; a partir do roster, development, picks e multas
                        monta um dicionário ctx com tudo pronto para renderização das abas.[file:697]
team_tabs_ui.py — Módulo de UI para teams; concentra o render das abas Principal, Development e Picks,
                  consumindo diretamente o ctx gerado pelo teams_page_context.[file:697]
teams_ui_helpers.py — Helpers visuais de teams.py; formatação de moeda, red flags, configuração de
                      colunas e summary cards.[file:692][file:683]

transactions_form_helpers.py — Helper novo da Sprint 2 para o formulário de transactions; centraliza
                                rótulos, coleta e validação de assets, builders de tx_row e
                                prepared_items, além de normalização de IDs para exibição.[code_file:708][file:693]
transactions_ui.py — Módulo novo da Sprint 2 para a aba Transactions; organiza o expander de nova
                     transaction, renderiza lados A/B, aciona validações e exibe o histórico com
                     filtros e normalização antes do st.dataframe.[code_file:709][file:683]

session_helpers.py — Helper da Sprint 1 para sessão, usuário atual, login obrigatório e logout; é a
                     fonte padrão de autenticação de página.[file:679][file:681][file:683]
role_helpers.py — Helper da Sprint 1 para identidade e papel do usuário, como is_admin_user e nome de
                  exibição.[file:681][file:690]
auth_ui.py — Helper da Sprint 1 para interface de login e troca obrigatória de senha, desacoplando
             essa UI de uni.py.[file:679][file:685]

Arquivos de dados e integração

roster.xlsx — Base operacional de elencos, picks e transactions usada pela página teams.py.[file:711]
Lista.xlsx — Arquivo auxiliar de dados/importação usado em rotinas anteriores do projeto.[file:600]
blog.xlsx — Arquivo auxiliar relacionado a conteúdo/home em versões anteriores.[file:612][file:613]

Sprint 2 — resumo das mudanças

- teams.py deixou de concentrar toda a lógica de roster, picks e formulário de transactions e passou
  a atuar como orquestrador de contexto (ctx) e chamadas para módulos de UI.[file:683][file:697]
- Criado teams_page_context.py para montar ctx com selected_team_id, visões de MAIN/DEV, picks,
  totais, posições, resumo e histórico de transactions.[file:697]
- Criado team_tabs_ui.py para encapsular o render das abas Principal, Development e Picks, usando
  apenas ctx como entrada.[file:697]
- Criado transactions_form_helpers.py para extrair as partes mais repetitivas e sensíveis do
  formulário de transactions (validações, builders, normalização de IDs).[code_file:708][file:693]
- Criado transactions_ui.py para retirar a aba Transactions de dentro de teams.py, tornando-a
  responsável por organizar o expander, os lados A/B e o histórico com filtros.[code_file:709][file:683]
- Ajustada a exibição do histórico de transactions para evitar erro do PyArrow ao converter colunas
  de ID e datas, garantindo que tipos mistos sejam tratados antes do st.dataframe.[file:693][code_file:709]

Regra de manutenção deste README

Sempre que um arquivo for atualizado, ajustar a linha dele neste documento com uma descrição curta
no formato:

nome_do_arquivo.py — para que serve hoje.

Exemplos de padrão:

uni.py — Arquivo principal e que deve ser rodado em Streamlit.[file:679]
teams.py — Arquivo de transactions e elencos, integrado ao uni.py, atuando como compositor das
           abas de roster/picks/transactions.[file:683][file:697]
