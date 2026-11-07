# Metodologia e limitações

## Equação

Para cada mês t:

`Ri,t − RFt = alpha + betaM (Mkt−RF)t + betaS SMBt + betaH HMLt + betaR RMWt + betaC CMAt + erro,t`

CAPM retém somente mercado. FF3 usa mercado, tamanho (SMB) e valor (HML). FF5 adiciona rentabilidade operacional (RMW) e investimento conservador versus agressivo (CMA). As definições e os portfólios são da biblioteca Kenneth French. SMB da família FF5 não é necessariamente igual ao SMB da família FF3; comparações entre modelos não são estritamente aninhadas quando se trocam as famílias.

Todos os retornos são simples e em decimal. O parser dos ZIPs converte percentuais dos fatores dividindo por 100; RF já é uma taxa mensal e não é dividida por 12. Sentinelas -99.99 e -999 são tratadas como ausentes antes da conversão. O bloco anual do arquivo é ignorado.

## Preços e alinhamento

1. Yahoo é consultado com `auto_adjust=True` (preços ajustados).
2. Último preço disponível em cada mês é usado, sem preenchimento de meses ausentes.
3. Retorno mensal = `P_m / P_(m−1) − 1`; por isso o primeiro mês de preços não produz retorno.
4. O mês corrente é removido. Calendários NYSE/BMF via pandas-market-calendars substituem a heurística de dias úteis: somente meses com cotação na última sessão esperada são considerados completos. O pacote modela as regras das bolsas, mas não é um serviço oficial delas. Suspensões, divergências de calendário e faltas de cotações exigem revisão manual. Não se garante completude de todos os pregões internos.
5. Datas são normalizadas para fim do mês, e ativo e fatores são alinhados por interseção.
6. Linhas com dados ausentes são descartadas. Se isso deixar um buraco interno, a análise é rejeitada: HAC e rolling pressupõem meses consecutivos.
7. Exige-se pelo menos 24 observações, fatores presentes, matriz de desenho de posto completo, valores finitos e ausência de duplicatas.

É recomendável consultar a partir do mês anterior ao início desejado para ter o preço-base do primeiro retorno. No CSV o usuário já fornece retornos mensais completos em USD; não há conversão cambial nem verificação automática de dividendos.

## Estimação e inferência

- OLS com constante explícita.
- Covariância HAC/Newey–West do statsmodels, kernel Bartlett padrão, `maxlags` configurável (padrão 3), sem correção de pequena amostra adicional.
- Estatísticas t, p-valores bilaterais e IC de 95% usando distribuição t com graus de liberdade residuais (`use_t=True`).
- HAC altera a inferência, não os coeficientes OLS. Sua validade é assintótica; 24 meses é apenas um limite operacional, não garantia de inferência confiável.
- Alpha anual aritmético = `12 × alpha mensal`. Não equivale a retorno composto realizável.
- Volatilidade residual anual = `desvio dos resíduos com ddof = número de parâmetros × sqrt(12)`. A anualização por raiz do tempo é uma convenção que pode ser inadequada na presença de dependência temporal.
- R² e R² ajustado medem ajuste dentro da amostra de retornos excedentes.
- Número de condição é reportado; posto completo não elimina multicolinearidade ou instabilidade.

Betas móveis usam OLS na janela selecionada com dados até aquele mês. Não têm IC/HAC apresentados. Janelas singulares são omitidas; amostra menor que a janela gera tabela vazia.

## Diagnósticos

| Medida | Hipótese/uso |
|---|---|
| Jarque–Bera (p) | Hipótese nula de normalidade dos resíduos |
| Breusch–Pagan LM (p) | Hipótese nula de homocedasticidade |
| Ljung–Box (p) | Ausência de autocorrelação até min(12, n // 5) defasagens |
| Durbin–Watson | Próximo de 2 sugere pouca autocorrelação de primeira ordem |

Esses diagnósticos usam implementações convencionais do statsmodels, não versões robustas para qualquer processo de erros. p pequeno é evidência contra a hipótese nula, não diagnóstico definitivo. Testar muitos ativos, janelas e modelos aumenta o risco de falsos positivos; não há ajuste para múltiplos testes.

## Limites econômicos e operacionais

- Não há causalidade, previsão, backtest, gestão de risco completa ou recomendação de investimento.
- Modelos podem omitir fatores relevantes e sofrer mudanças de regime, exposição dinâmica, endogeneidade e viés de seleção/sobrevivência.
- Fatores são portfólios long-short, não retornos garantidos de produtos investíveis; custos de implementação não estão incluídos.
- Dados públicos podem ser revisados, atrasar ou mudar de formato. Cache em disco não expira automaticamente e não oferece proveniência institucional ou versionamento histórico imutável.
- A versão 0.2 adiciona snapshots SHA-256 e versões dos dados; veja [research.md](research.md). Isso não certifica autenticidade institucional.
- Não existe fallback para números sintéticos quando a rede falha. O modo de demonstração é identificado explicitamente.
- Regressão de ativo americano em USD não se transfere automaticamente para B3/BRL, títulos, opções ou criptoativos.
- Testes verificam comportamento computacional e integração, não certificam os dados de terceiros nem validade de uma estratégia.
