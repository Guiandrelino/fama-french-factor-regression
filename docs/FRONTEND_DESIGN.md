# Interface institucional — camada de apresentação

Backup anterior: tag Git `backup-frontend-20261107`, criada antes das alterações.

## Arquitetura

- `src/ui/theme.py`: tokens, paleta e template Plotly global.
- `src/ui/theme.css`: único CSS global, variáveis, seletores estáveis e responsividade.
- `src/ui/components.py`: top bar, seções, notas, painéis, KPIs, tabelas brasileiras e rodapé.
- `src/factorlab/ui.py`: ponte de compatibilidade dos pontos de entrada e autenticação existente.
- `app.py`, `pages/2_Pesquisa.py`, `research_ui.py`, `advanced_ui.py`: composição das telas, sem CSS inline.
- `.streamlit/config.toml`: tema base coerente com os tokens.

Superfícies #0A0E14, #0F151D, #151C26; acento #8CAED0; positivo #80B69B; negativo #D89B9B. IBM Plex Sans para interface, IBM Plex Mono para números (Google Fonts com fallback local). Nenhuma dependência Python nova.

Tabelas usam Styler sem alterar DataFrames: zebra, números alinhados à direita, vírgula decimal, sinal negativo e cor condicional. Percentuais são formatados somente em campos com unidade definida; coeficientes e intervalos permanecem decimais quando misturam alpha e betas. Template Plotly compartilhado com superfícies transparentes, legenda compacta, cores sóbrias e hover unificado. Retornos e patrimônio recebem unidades específicas; matrizes/betas não são convertidos para percentuais.

## Validação

Comparação exata de métricas e coeficientes antes/depois para CAPM, FF3, FF5, Carhart4 e FF6: idênticos. Snapshot de validação local em outputs/frontend-numeric-baseline.json (não versionado).

82 testes offline e dois testes Chromium aprovados. Navegação manual automatizada no Chromium: página individual (vazia e estimada), Pesquisa, quatro estações, cinco abas de risco/carteira e quatro módulos operacionais sem exceções. Desktop 1600px e tela 390px sem overflow horizontal. Capturas locais em outputs/institutional-*.png.

Não foram alterados cálculos, fontes de dados ou funções financeiras. Fontes externas exigem conectividade; Google Fonts pode ser bloqueado e então o fallback é usado. Não se removem esses limites operacionais com CSS.
