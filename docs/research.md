# Pesquisa — versão 0.2

Abra o app com `python -m streamlit run app.py` e clique no link **Abrir Pesquisa** ou na página Pesquisa da navegação lateral.

## Ativos e carteira

Informe ativos separados por vírgula e um benchmark. O benchmark é baixado mesmo quando não está na lista. Yahoo utiliza preços ajustados; CSV utiliza `date,AAPL,MSFT,SPY,...`, retornos totais simples em decimal, na moeda escolhida, nunca preços. Todos os modelos e ativos usam exatamente a mesma interseção de meses completos e finitos. Ausências internas são rejeitadas, não preenchidas. Na demonstração os nomes são apenas rótulos de séries sintéticas.

Pesos aceitam `AAPL: 30%` ou `AAPL: 0.3`, um por linha. Devem ser não negativos, finitos e somar 100%; não há alavancagem. Campo vazio desativa carteira.

- `monthly`: rebalanceamento para os pesos informados no início de cada mês.
- `buy_hold`: compra inicial na amostra comum; quantidades mantidas, pesos variam conforme retornos acumulados. Eventos de dividendos são representados pelo retorno total ajustado, sem caixa separado.

Não há custos, impostos, aportes ou execução real. A carteira começa na amostra comum, não antes. Pesos exportados são do início do mês. Retorno ativo aritmético anual = 12 × média da diferença de retornos; tracking error = desvio da diferença × √12. Não é alpha de regressão contra o benchmark.

## Modelos e estabilidade

EUA: CAPM, FF3, FF5, CARHART4 (FF3 + momentum) e FF6 (FF5 + momentum). FF6 aqui significa **FF5 + Mom**, não uma especificação oficial única. FF3 e FF5 usam suas próprias famílias de SMB. Brasil: CAPM, FF3 e CARHART4 a partir dos fatores NEFIN, sem RMW/CMA.

A tabela inclui alpha e IC mensal, R², R² ajustado, volatilidade residual, RMSE, AIC/BIC gaussianos convencionais e `rolling_std_*` (desvio entre estimativas móveis, não teste formal). Os modelos não são automaticamente classificados como melhores/piores. Critérios de informação não são robustos a qualquer dependência dos erros e não substituem diagnóstico.

## Walk-forward

Janela fixa de treinamento com pelo menos 24 meses. Para cada mês de avaliação, betas usam somente meses anteriores; a resposta explicada usa os fatores **realizados** no mês de avaliação. Logo, mede estabilidade explicativa fora da amostra, **não previsão negociável**. A janela de treino é controlável; reexecute com janelas diferentes para avaliar sensibilidade. Os arquivos exportam `train_end`, betas e erros por data.

Além dessa avaliação explicativa, há **previsão ex ante**: modelo separado de retorno total do mês t sobre fatores t-L, com L configurável (padrão 2 meses). Cada janela usa somente respostas anteriores, e compara a previsão à média histórica calculada no treino. Exporta previsão, resposta, erros, fim do treino e último mês de fatores. Não usa fatores contemporâneos nem RF futuro. A defasagem pressupõe disponibilidade; sem arquivos históricos point-in-time, revisões e datas efetivas de publicação ainda impedem certificar um backtest negociável. Não se promete poder preditivo ou lucro.

## Relatório e pacote

HTML autônomo inclui resumo, equações, tabelas, gráfico interativo, diagnósticos, interpretação do IC do alpha, fontes, parâmetros e limitações. ZIP contém HTML, manifesto, tabela consolidada, retornos, detalhes por ativo/modelo, pesos e walk-forward. PDF nativo é gerado por ReportLab no servidor, sem Chromium ou serviço externo; inclui gráfico vetorial, equações, tabelas, diagnósticos e manifesto. Disponível como download separado e dentro do ZIP.

## Rastreabilidade e calendários

Snapshots SHA-256 em `.cache/snapshots/`, metadados de downloads `.meta.json`, timestamp UTC, parâmetros, versões das bibliotecas e hash dos dados processados no manifesto. Preços ajustados e CSV de entrada também recebem snapshots. O hash identifica conteúdo, não certifica sua autenticidade. Cache legado recebe data de registro explicitamente identificada, não uma data inventada de download. Atualização e alertas estão na página Pesquisa. Cache com 7 dias é sinalizado; isso não significa que os fatores já tenham nova observação publicada.

Calendários NYSE e BMF são obtidos de `pandas-market-calendars`, que modela as regras oficiais, mas não é uma API oficial da bolsa. Cada mês precisa conter cotação na última sessão esperada; mês corrente é excluído. Não garante que todos os pregões internos estejam presentes. Diferenças de calendário ou lacunas do Yahoo são rejeitadas quando quebram a sequência mensal. Em BOVA11.SA foi observada falta de fechamento esperado em dezembro/2017 na consulta local: use intervalo contínuo posterior ou fonte de retornos verificada; não há preenchimento silencioso.

## NEFIN e Brasil

Fonte verificada: https://nefin.com.br/data/risk-factors/ e CSV `https://nefin.com.br/nefindata/risk-factors/nefin_factors_monthly.csv`.

A página declara uso gratuito para acadêmicos e profissionais e solicita citação em trabalhos publicados. Cite **NEFIN (2026). Risk Factors. Center for Research in Financial Economics, Universidade de São Paulo.** Não se assume licença irrestrita para redistribuição comercial; confirme os termos diretamente com o provedor antes de distribuir dados. O relatório incorpora atribuição via manifesto da fonte; dados não são empacotados no repositório.

Integração usa versão mensal **value-weighted**, com retornos em frações, não percentuais. Usa o spread de retornos mensais publicado pelo provedor, não composição dos spreads diários. `Rm_minus_Rf → Mkt-RF`, `WML → Mom`, `Risk_Free → RF`. IML não faz parte dos modelos atuais. Não misture NEFIN com retornos em USD. Yahoo Brasil aceita somente tickers `.SA`, com exemplo de benchmark `BOVA11.SA`; no CSV a moeda é responsabilidade do usuário. Metodologia: https://nefin.com.br/nefindata/methodology/nefin_methodology.pdf.

## Automação e Docker

`.github/workflows/quality.yml`: Python 3.11/3.12/3.13, lint, formato e cobertura em push/PR; Chromium em job separado; live somente semanalmente ou por execução manual. Requer publicar o repositório no GitHub para executar. O workflow inclui build e smoke test Docker. Execução remota depende de um repositório GitHub configurado; a pasta local ainda não é repositório Git e não possui remote/autenticação configurados, portanto não foi possível disparar Actions remotamente.

```sh
docker build -t factorlab .
docker run --rm -p 8501:8501 -v factorlab-cache:/app/.cache factorlab
```

Imagem executa como usuário não root e tem healthcheck. Build local validado com `docker build -t factorlab:local .`; container iniciou, healthcheck ficou healthy, endpoint retornou ok e regressão + PDF nativo foram executados dentro dele. Container de validação foi removido ao final. Isso não equivale à execução remota de CI.
