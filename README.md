# FactorLab · Fama–French Factor Regression

Projeto Python com dashboard Streamlit e CLI para estimar CAPM, Fama–French 3 fatores e 5 fatores em retornos mensais de ativos americanos em USD. Inclui erros-padrão HAC/Newey–West, diagnósticos, betas móveis e exportação.

## Novidades da versão 0.2 · página Pesquisa

Comparação de ativos e benchmark, carteira com rebalanceamento mensal ou buy-and-hold, comparação em amostra comum, momentum, Brasil/NEFIN, walk-forward, relatório HTML, ZIP consolidado e rastreabilidade SHA-256.

**[Guia completo da página Pesquisa](docs/research.md)**. Abra pelo link na página inicial ou navegação lateral. Inclui instruções de CI e Docker, metodologia da carteira, calendários NYSE/BMF e termos de uso da fonte brasileira. PDF nativo disponível por ReportLab, além do HTML e ZIP. Previsão ex ante com fatores defasados é separada da avaliação explicativa.

## Instalação (Windows / PowerShell)

Requer Python 3.11 ou superior (validado localmente no Python 3.13).

```powershell
py -3.13 -m venv .venv
.\.venv\Scripts\python.exe -m pip install -e ".[dev]"
.\.venv\Scripts\python.exe -m streamlit run app.py
```

Não é necessário ativar o ambiente. Se preferir: ` .\.venv\Scripts\Activate.ps1`.
No Linux/macOS, use `python3 -m venv .venv` e `.venv/bin/python` nos comandos.

Para reproduzir as versões da validação local em Python 3.13:

```powershell
.\.venv\Scripts\python.exe -m pip install -r requirements-lock.txt
.\.venv\Scripts\python.exe -m pip install -e . --no-deps
```

O lock representa este ambiente Windows; a instalação pelo `pyproject.toml` é a alternativa multiplataforma. NumPy está limitado a `<2.4` por compatibilidade com pandas 2.x; warnings são tratados como erros nos testes. Streamlit usa a API atual `width="stretch"`.

## Dashboard

1. Selecione **Demonstração offline**, **Yahoo Finance** ou **CSV próprio**.
2. Escolha CAPM, FF3 ou FF5, intervalo, defasagens HAC e janela móvel.
3. Clique em **Executar análise**.
4. Examine coeficientes, IC de 95%, resíduos e exposições móveis.
5. Na aba **Dados e exportação**, baixe coeficientes, observações e betas móveis.

A demonstração é sintética, reproduzível (seed 42, 2010–2024) e ignora o intervalo selecionado. Nunca substitui silenciosamente um download que falhou. Alterar controles não recalcula resultados até clicar no botão; uma nova execução que falha remove os resultados anteriores.

### CSV de retornos

Use vírgula como separador, ponto decimal e uma observação por mês:

```csv
date,return
2020-01-31,0.025
2020-02-29,-0.04
```

`0.025` significa **2,5%**, não 0,025%. O arquivo deve conter **retornos totais simples mensais em USD**, incluindo dividendos, antes de subtrair RF. Não envie preços, retornos logarítmicos ou valores já excedentes. Datas são normalizadas para fim do mês; duplicatas mensais, datas ausentes, infinito e retornos inferiores a -100% são rejeitados. São necessários pelo menos **24 meses consecutivos em comum com os fatores**. O exemplo acima ilustra somente o formato, não tem observações suficientes para estimar o modelo.

O usuário é responsável por fornecer meses completos no CSV. A origem e a moeda não podem ser verificadas automaticamente.

## CLI

```powershell
.\.venv\Scripts\factorlab.exe --demo --model FF5 --output outputs/demo
.\.venv\Scripts\factorlab.exe --ticker AAPL --model FF3 --start 2015-01-01 --end 2025-01-01 --output outputs/aapl
.\.venv\Scripts\factorlab.exe --csv meus_retornos.csv --model CAPM --output outputs/csv
```

Opções: `--hac-lags 3`, `--window 36`, `--refresh` (rebaixa fatores). `--end` no Yahoo é exclusivo. Os limites de seleção do CSV usam o fatiamento de datas do pandas (inclusivo). Na demonstração, datas não são aplicadas.

Saídas: `coefficients.csv`, `observations.csv`, `rolling.csv` e `report.json`. O JSON contém fonte, modelo, intervalo efetivo, métricas e diagnósticos.

## Metodologia

Veja [docs/methodology.md](docs/methodology.md) para equações, construção da amostra, inferência e limitações.

- **CAPM:** Mkt−RF.
- **FF3:** Mkt−RF, SMB e HML, da família FF3.
- **FF5:** Mkt−RF, SMB, HML, RMW e CMA, da família FF5.
- OLS com intercepto, resposta `retorno do ativo − RF` e covariância HAC, inferência t.
- Alpha anual exibido = `12 × alpha mensal` (não retorno composto).
- Betas móveis calculados por OLS retrospectivo, sem previsão nem IC.

## Testes e qualidade

```powershell
# Testes determinísticos, sem internet
.\.venv\Scripts\python.exe -m pytest -q
.\.venv\Scripts\python.exe -m ruff check .
.\.venv\Scripts\python.exe -m ruff format --check .

# Integração real: SPY, AAPL, MSFT e IWM × CAPM, FF3 e FF5
.\.venv\Scripts\python.exe -m pytest -q -m live

# Upload real no Chromium: servidor isolado, dados sintéticos locais
.\.venv\Scripts\python.exe -m playwright install chromium
.\.venv\Scripts\python.exe -m pytest -q -m browser
```

Testes `live` e `browser` não rodam por padrão. A suíte offline compara coeficientes, HAC, p-valores e intervalos com statsmodels, recupera parâmetros conhecidos e cobre falhas de dados, cache, rede simulada, CLI e dashboard. O teste Chromium envia CSV pelo widget real, executa a análise, baixa o arquivo de coeficientes e confirma a mensagem de erro após um upload inválido.

Detalhes e resultados: [docs/validation.md](docs/validation.md). Testes live dependem de disponibilidade, limites e revisões de dados das fontes externas; não são prova de acurácia econômica dos dados.

## Estrutura

```text
app.py                      Dashboard
src/factorlab/data.py        Downloads, parser, retornos e CSV
src/factorlab/regression.py  OLS, HAC, diagnósticos e rolling
src/factorlab/cli.py         Execução e exportação por terminal
tests/                      Unitários, integração, dashboard e navegador
docs/                       Metodologia e validação
```

## Fontes e limitações

- [Kenneth French Data Library](https://mba.tuck.dartmouth.edu/pages/faculty/ken.french/data_library.html): fatores americanos mensais; o ZIP é armazenado em `.cache/` e reutilizado até remoção ou `--refresh` na CLI. O dashboard também usa cache em memória de uma hora. Excluir `.cache/` e reiniciar o app força nova obtenção.
- [yfinance](https://github.com/ranaroussi/yfinance): preços Yahoo com ajuste automático de dividendos/splits; não é uma fonte licenciada de nível institucional. Respeite os termos das fontes.
- A página inicial e CLI usam fatores americanos/USD. Para Brasil/BRL, use a página Pesquisa com NEFIN; não há FF5 brasileiro neste dataset. Não há negociação, custos ou previsão de preços.
- R² alto não significa rentabilidade futura, e alpha significativo não prova habilidade. Leia as limitações econométricas no documento de metodologia.

Projeto para análise e educação, **não recomendação de investimento**.
