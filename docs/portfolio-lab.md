# Risk & Portfolio Lab

Na página **Pesquisa**, execute uma análise e encontre as cinco ferramentas abaixo. Yahoo Finance é agora a fonte padrão; não há conversão silenciosa para dados sintéticos. Dados reais são obtidos via yfinance (preços ajustados), Kenneth French (EUA/USD) e NEFIN (Brasil/BRL). Não são cotações em tempo real. Falhas de DNS ou limites externos podem impedir downloads; alternativamente use CSV de retornos totais mensais verificados, com a moeda correspondente aos fatores.

## 1. Decomposição de risco

Contribuição anualizada do fator i = `12 × beta_i × (Cov(F) beta)_i`. Essa decomposição inclui covariâncias e pode ter contribuições negativas. Soma das contribuições sistemáticas mais variância residual amostral reconcilia a variância do retorno excedente OLS dentro da amostra. Aqui a variância residual usa ddof=1 para reconciliação; não é a estimativa corrigida pelos graus de liberdade exibida na regressão original. Anualização ×12 não inclui autocovariâncias. Ex post, não previsão.

## 2. Cenários e estresse

Choques manuais em percentuais dos retornos dos fatores. Impacto = soma de beta × choque; não inclui alpha, RF ou ruído residual. Cenários históricos reaplicam retornos de fatores observados aos betas da análise atual. Não representam posições históricas nem perda máxima, VaR ou recomendação. Cenário fora da amostra é informado, sem números inventados.

## 3. Salvar e comparar

SQLite em `.cache/analyses.sqlite`: nome, timestamp UTC, metadados, tabela e retornos. Somente JSON/CSV; não carrega objetos pickle. Comparação retorna segunda menos primeira nos ativos/modelos comuns. Confira moeda, fonte e intervalo: diferenças entre amostras não são teste de melhora. Exclusão remove o registro, não os snapshots. Em Docker, persista `/app/.cache` para manter as análises.

O banco é local e compartilhado por sessões deste servidor; não há autenticação. Não disponibilize carteiras privadas em um deploy público sem isolamento de usuários e controle de acesso.

## 4. Diagnósticos

Correlação dos fatores, VIF com intercepto, distância de Cook, leverage, resíduos studentizados internos e sensibilidade HAC em 0/3/6/12 lags. Cook >4/n é apenas triagem, não exclusão automática. Influência OLS convencional não é diagnóstico robusto universal. Não se implementou teste formal de quebra estrutural nesta etapa.

## 5. Otimização com restrições

Mínima variância via SLSQP: long-only, soma 100%, limite por ativo, covariância regularizada em direção à diagonal e limites opcionais de beta de mercado. Rejeita restrições inviáveis. Treino mínimo 24 meses; teste mínimo 12 meses. Covariância e betas de restrição são estimados apenas no treino. Pesos aplicados ao holdout são constantes com rebalanceamento mensal; referência equiponderada. Sem custos, impostos ou promessa de rentabilidade. Seleção prévia do universo pode introduzir sobrevivência/viés. Betas realizados no holdout podem diferir dos limites estimados.

## Exportação

Risco, cenário e diagnósticos selecionados entram nos extras do ZIP; suas seleções são identificadas na tabela. Pesos otimizados e holdout possuem downloads próprios. Análises salvas exportam resumo em CSV.

## Validação desta entrega

72 testes offline aprovados; teste Chromium aprovado; Ruff lint e formato aprovados. Testes incluem reconciliação de variância, choques, SQLite, VIF, sensibilidade HAC, restrições e ausência de uso do holdout para estimar pesos. A suíte live nesta execução foi interrompida após timeouts DNS do Yahoo; não está declarada aprovada nesta versão. Integração real permanece disponível, sem fallback silencioso.
