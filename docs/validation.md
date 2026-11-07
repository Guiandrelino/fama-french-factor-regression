# Validação

## Última validação · correções adicionais

- 67 testes offline aprovados, incluindo retry transitório/esgotamento, PDF nativo e ausência de vazamento contemporâneo na previsão defasada.
- 23 testes live aprovados (20 combinações EUA e 3 Brasil) na última execução após adição de retry limitado com backoff. DNS continua sendo dependência externa; retries não garantem disponibilidade permanente.
- Chromium aprovado, lint e formato aprovados.
- Build Docker local concluído; container healthy, HTTP health `ok`, regressão e PDF nativo testados dentro do container.
- GitHub Actions executado remotamente com sucesso após configurar o repositório: [execução completa 42396234673](https://github.com/Guiandrelino/fama-french-factor-regression/actions/runs/42396234673), commit `988484c`. Aprovados Python 3.11/3.12/3.13, Chromium, container Docker e integração live. Corridas de rerun/upload do Streamlit observadas no Linux foram corrigidas com sincronização e tentativas limitadas no teste de navegador.
- Previsão ex ante adicionada sem fatores contemporâneos. Ainda não é certificação de backtest investível point-in-time.

## Validação anterior · versão 0.2

- 63 testes offline aprovados; cobertura do pacote: **91%**.
- Teste Chromium aprovado: upload/download da página inicial e upload multivariado com carteira e exportação ZIP na página Pesquisa.
- Ruff lint/formato aprovados.
- Suíte live ampliada para 20 combinações EUA + 3 Brasil. A última execução **não passou**: timeouts de resolução DNS do Yahoo causaram falhas nos downloads. Não foram convertidos em skip nem contados como aprovação. Uma execução intermediária confirmou três modelos brasileiros e CAPM/SPY, mas isso não substitui validação completa.
- Downloads de fatores NEFIN e momentum foram verificados durante a implementação.
- CI remoto e container Docker ainda não executados neste ambiente.

Os resultados históricos abaixo descrevem a versão anterior e não substituem o estado atual. Veja [research.md](research.md).

## Ambiente

Validação local no Windows, Python 3.13. Versões exatas em `requirements-lock.txt`.

## Cobertura

- CAPM, FF3 e FF5: comparação independente com chamadas diretas de statsmodels para coeficientes, erros HAC, p-valores, intervalos, ajuste e rolling.
- Recuperação de parâmetros conhecidos com ruído pequeno e seed fixo.
- Falhas: menos de 24 meses, fatores ausentes, duplicatas, meses faltantes, infinito, perdas inválidas, matriz singular, índice incorreto, datas ausentes, HAC/janela inválidos.
- Dados: conversão percentual/decimal, sentinelas, separação mensal/anual, CSV, mês corrente e ausência de preenchimento de preços.
- Integração isolada: download/cache/refresh com mocks, timeout, preços vazios e exportação CLI.
- Dashboard com AppTest: três modelos, erro de upload ausente, datas inválidas e falha de rede sem resultados antigos.
- Chromium/Playwright: envio de CSV real pelo widget, execução da análise, download verificável dos coeficientes, substituição por CSV inválido e remoção de resultados antigos. Usa fatores sintéticos locais em cache num diretório temporário, sem rede externa. Não simula o widget de upload.
- Integração live: SPY, AAPL, MSFT e IWM nos três modelos (12 combinações), preços de janeiro/2015 até janeiro/2025 exclusivo. A amostra esperada inicia em fevereiro/2015 porque janeiro fornece o preço-base.

## Execução e escopo

```powershell
.\.venv\Scripts\python.exe -m pytest -q
.\.venv\Scripts\python.exe -m pytest -q -m browser
.\.venv\Scripts\python.exe -m pytest -q -m live
.\.venv\Scripts\python.exe -m ruff check .
.\.venv\Scripts\python.exe -m ruff format --check .
```

Resultado da execução local nesta entrega:

| Verificação | Resultado |
|---|---|
| Suíte offline | 45 passaram; 13 testes externos separados |
| Chromium (upload e download reais) | 1 passou |
| Integração live (4 ativos × 3 modelos) | 12 passaram |
| Ruff lint | Sem erros |
| Ruff format | Todos os arquivos formatados |

Total: **58 testes aprovados**, sem warnings Python na saída das suítes. `live` e `browser` são opt-in. Não se deve ignorar falhas de rede como testes aprovados. O teste live usa o cache local de fatores quando presente; para validar também seu download, remova `.cache/` antes da execução.

Warnings Python são erros na suíte; mensagens de log do harness AppTest sobre ausência de ScriptRunContext não são warnings de compatibilidade da aplicação. A captura abrangente de exceções é intencional somente nas fronteiras CLI/UI; na UI há registro do traceback para diagnóstico.

## Limitações da validação

O teste de upload cobre um CSV válido e um inválido no Chromium, não todos os navegadores, tamanhos de arquivo ou condições de rede. Integração live verifica execução, finitude e sanidade, não valores fixos de coeficientes, pois fontes externas revisam dados. O teste sintético e a comparação com statsmodels oferecem referências determinísticas complementares, mas não constituem auditoria financeira.
