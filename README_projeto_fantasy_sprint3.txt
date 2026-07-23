Arquivo de controle da Sprint 3 do projeto Fantasy NBA.
A ideia é manter este documento sempre atualizado quando algum arquivo for criado, alterado ou passar a ter nova responsabilidade.

Sprint 3 — foco principal

- Modularizar home.py, classificacao.py e lei.py.
- Separar contexto, renderização e regras de domínio.
- Manter o comportamento atual estável enquanto os arquivos principais ficam menores.

Arquivos principais

uni.py — Shell principal da aplicação; configura Streamlit, executa startup, controla login/logout,
         troca obrigatória de senha e abre as páginas integradas.[file:679][file:685][file:688]
home.py — Página Home da liga; nesta sprint deve deixar de concentrar toda a lógica de abas e passar
          a orquestrar helpers de contexto e UI.[file:681][file:689]
teams.py — Página de elencos e transactions já consolidada na Sprint 2; permanece como compositor de
           contexto + abas e serve como base estável para as próximas etapas.[file:683][file:697][code_file:708][code_file:709]
lei.py — Página do leilão integrada ao shell principal; nesta sprint deve ser dividida em UI pública
         e UI administrativa, com services permanecendo responsáveis pelo domínio.[file:682][file:687]
classificacao.py — Página de classificação integrada ao shell principal; deve sair da mistura entre
                  cálculos e UI, deixando os cálculos em helper/service separado.[file:680]

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

Helpers e serviços centrais da Sprint 3

teams_page_context.py — Helper de contexto de teams; já consolidado na sprint anterior, continua
                        fornecendo ctx pronto para a página de elencos.[file:697]
team_tabs_ui.py — Módulo de UI para teams; renderiza as abas Principal, Development e Picks.[file:697]
transactions_form_helpers.py — Helper da Sprint 2 para o formulário de transactions; permanece como
                                suporte estável para as regras já validadas.[code_file:708][file:693]
transactions_ui.py — Módulo da Sprint 2 para a aba Transactions; permanece como UI separada e estável
                     enquanto a Sprint 3 foca outras páginas.[code_file:709][file:683]
teams_ui_helpers.py — Helpers visuais de teams.py; formatação de moeda, red flags, configuração de
                      colunas e summary cards.[file:692][file:683]

auth_ui.py — Helper da Sprint 1 para interface de login e troca obrigatória de senha.
session_helpers.py — Helper da Sprint 1 para sessão, usuário atual, login obrigatório e logout.
role_helpers.py — Helper da Sprint 1 para identidade e papel do usuário, como is_admin_user e nome de
                  exibição.[file:679][file:681][file:690]

Arquivos de dados e integração

roster.xlsx — Base operacional de elencos, picks e transactions usada pela página teams.py.[file:711]
Lista.xlsx — Arquivo auxiliar de dados/importação usado em rotinas anteriores do projeto.[file:600]
blog.xlsx — Arquivo auxiliar relacionado a conteúdo/home em versões anteriores.[file:612][file:613]

Sprint 3 — resumo do plano

- Home será quebrada em contexto + UI, deixando o arquivo principal mais leve.[file:681][file:689]
- Classificação terá os cálculos movidos para um helper/service próprio, com a página cuidando só da exibição.[file:680]
- Leilão será separado entre fluxo público e administrativo, preservando as regras de domínio em auction_v5.py.[file:682][file:687]
- teams.py e o fluxo de transactions permanecem estáveis, servindo como base já concluída da Sprint 2.[file:683][file:697][code_file:708][code_file:709]

Ordem de execução da Sprint 3

1. Home.
2. Classificação.
3. Leilão.

Essa ordem é a mais segura porque Home tem a maior mistura de responsabilidades, Classificação é mais previsível e Leilão é o módulo mais sensível.[file:681][file:680][file:682][file:689][file:687]

Regra de manutenção deste README

Sempre que um arquivo for atualizado, ajustar a linha dele neste documento com uma descrição curta no formato:

nome_do_arquivo.py — para que serve hoje.

Exemplos de padrão:

uni.py — Arquivo principal e que deve ser rodado em Streamlit.[file:679]
teams.py — Arquivo de elencos e transactions, integrado ao uni.py, atuando como compositor das
           abas de roster/picks/transactions.[file:683][file:697]
home.py — Página da Home que deve passar a orquestrar contexto + UI na Sprint 3.[file:681][file:689]
lei.py — Página do leilão que deve ser dividida entre UI pública e administrativa na Sprint 3.[file:682][file:687]
classificacao.py — Página de classificação que deve ficar focada em exibição na Sprint 3.[file:680]
