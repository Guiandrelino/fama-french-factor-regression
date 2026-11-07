"""Execute com: streamlit run app.py."""

import logging
from datetime import date

import pandas as pd
import plotly.express as px
import streamlit as st

from factorlab.data import demo_data, load_factors, load_prices, monthly_returns, read_returns_csv
from factorlab.regression import MODELS, fit_model
from factorlab.ui import context_strip, setup_terminal

st.set_page_config(page_title="FactorLab | Research Terminal", page_icon="▥", layout="wide")
setup_terminal("Factor regression")
st.title("FATOR / Estação de análise")
st.caption("REGRESSÃO DE RETORNOS EXCEDENTES   •   MENSAL   •   USD   •   OLS / HAC")
st.page_link(
    "pages/2_Pesquisa.py",
    label="Abrir Pesquisa: múltiplos ativos, carteira e relatórios",
    icon="↗",
)


def market_data(ticker, start, end, model):
    return monthly_returns(load_prices(ticker, str(start), str(end))), load_factors(model)


def french_data(model):
    return load_factors(model)


with st.sidebar:
    st.markdown("### ▥ Research controls")
    st.caption("PARÂMETROS DA REGRESSÃO")
    source = st.radio("Fonte", ["Demonstração offline", "Yahoo Finance", "CSV próprio"])
    model = st.selectbox("Modelo", list(MODELS), index=2)
    ticker = st.text_input("Ticker americano", "SPY").strip().upper()
    start = st.date_input(
        "Início",
        date(2015, 1, 1),
        min_value=date(1926, 1, 1),
        max_value=date.today(),
        key="start_date",
    )
    end = st.date_input(
        "Fim (exclusivo no Yahoo)",
        date.today(),
        min_value=date(1926, 1, 1),
        max_value=date.today(),
        key="end_date",
    )
    uploaded = (
        st.file_uploader("CSV: date,return (decimal, USD)", type="csv")
        if source == "CSV próprio"
        else None
    )
    lags = st.slider("Defasagens HAC / Newey–West", 0, 12, 3)
    window = st.slider("Janela móvel (meses)", 24, 120, 36, step=12)
    run = st.button("Executar análise", type="primary", width="stretch")
    st.caption("Dados reais exigem internet. A demonstração não faz downloads.")

if run:
    st.session_state.pop("analysis", None)
    try:
        if start >= end:
            raise ValueError("A data inicial deve ser anterior à final.")
        with st.spinner("Carregando dados e estimando regressão…"):
            if source == "Demonstração offline":
                returns, factors = demo_data()
                label = "SINTÉTICO · seed 42 · 2010–2024 (intervalo de datas ignorado)"
            elif source == "Yahoo Finance":
                returns, factors = market_data(ticker, start, end, model)
                label = f"{ticker} · Yahoo Finance + Kenneth French"
            else:
                if uploaded is None:
                    raise ValueError("Envie um CSV para continuar.")
                returns = read_returns_csv(uploaded).loc[str(start) : str(end)]
                factors = french_data(model)
                label = "CSV do usuário + Kenneth French"
            result = fit_model(returns, factors, model, lags, window)
            st.session_state["analysis"] = (result, label, len(returns), window)
    except Exception as exc:
        logging.getLogger(__name__).exception("Falha na análise do dashboard")
        st.error(f"Não foi possível concluir a análise: {exc}")

if "analysis" not in st.session_state:
    context_strip(
        [
            ("WORKSPACE", "Regressão de fatores"),
            ("UNIVERSO", "EUA / USD"),
            ("FREQUÊNCIA", "Mensal"),
            ("INFERÊNCIA", "OLS + Newey–West"),
        ]
    )
    st.markdown(
        '<div class="desk-command"><span>FATOR &lt;GO&gt;</span> CONFIGURE O UNIVERSO → EXECUTE → INSPECIONE O RISCO</div>',
        unsafe_allow_html=True,
    )
    left, right = st.columns([1.65, 1], gap="small")
    with left:
        st.markdown(
            '<div class="panel-title">01 / MATRIZ DE MODELOS <span>ESPECIFICAÇÕES DISPONÍVEIS</span></div>',
            unsafe_allow_html=True,
        )
        matrix = pd.DataFrame(
            {
                name: {
                    factor: ("●" if factor in columns else "—")
                    for factor in ["Mkt-RF", "SMB", "HML", "RMW", "CMA", "Mom"]
                }
                for name, columns in MODELS.items()
            }
        ).T
        matrix.index.name = "Modelo"
        st.dataframe(matrix, width="stretch", height=245)
        st.markdown('<div class="panel-title">02 / EQUAÇÃO DO MODELO</div>', unsafe_allow_html=True)
        st.code("Ri − RF = α + β × F + ε", language=None)
        st.caption(
            "Alpha mensal em decimal · betas adimensionais · intervalos de 95% com covariância HAC."
        )
    with right:
        st.markdown(
            '<div class="panel-title">03 / TICKET DE PESQUISA <span>NÃO EXECUTADO</span></div>',
            unsafe_allow_html=True,
        )
        ticket = pd.DataFrame(
            {
                "Parâmetro": [
                    "Fonte",
                    "Ativo solicitado",
                    "Modelo",
                    "Início",
                    "Fim",
                    "HAC / lags",
                    "Janela móvel",
                ],
                "Configuração": [
                    source,
                    ticker,
                    model,
                    str(start),
                    str(end),
                    str(lags),
                    f"{window} meses",
                ],
            }
        )
        st.dataframe(ticket, hide_index=True, width="stretch", height=280)
        st.warning("SEM RESULTADOS · configure os controles à esquerda e execute a análise.")
    st.markdown('<div class="panel-title">04 / PROTOCOLO DE LEITURA</div>', unsafe_allow_html=True)
    st.markdown(
        '<div class="desk-protocol"><div><b>01 ORIGEM</b><br>Dados reais exigem rede. Demonstração é identificada como sintética.</div><div><b>02 INFERÊNCIA</b><br>IC do alpha incluindo zero não sustenta alpha diferente de zero.</div><div><b>03 RISCO</b><br>Inspecione resíduos e estabilidade. Ajuste histórico não é previsão.</div></div>',
        unsafe_allow_html=True,
    )
else:
    result, label, input_count, used_window = st.session_state["analysis"]
    st.subheader(f"{result.model} · {label}")
    st.caption(
        f"Amostra efetiva: {result.data.index.min():%m/%Y} — "
        f"{result.data.index.max():%m/%Y} · {len(result.data)} meses · "
        f"{input_count - len(result.data)} retornos fora da amostra comum. "
        "Resultados abaixo correspondem à última execução."
    )
    if label.startswith("SINTÉTICO"):
        st.warning("Demonstração sintética: estes números não representam um ativo real.")
    context_strip(
        [
            ("MODELO", result.model),
            ("AMOSTRA", f"{len(result.data)} meses"),
            ("PERÍODO", f"{result.data.index.min():%m/%Y} → {result.data.index.max():%m/%Y}"),
            ("COVARIÂNCIA", f"HAC / {result.metrics['hac_lags']} lags"),
        ]
    )
    metrics = st.columns(4)
    metrics[0].metric("R² ajustado", f"{result.metrics['adjusted_r_squared']:.1%}")
    metrics[1].metric("Alpha mensal", f"{result.metrics['alpha_monthly']:.3%}")
    metrics[2].metric("Alpha anual (12 × α)", f"{result.metrics['alpha_annual_arithmetic']:.2%}")
    metrics[3].metric("Vol. residual anualizada", f"{result.metrics['residual_vol_annual']:.2%}")
    tabs = st.tabs(["Coeficientes", "Ajuste e resíduos", "Exposição móvel", "Dados e exportação"])
    with tabs[0]:
        st.dataframe(result.coefficients.style.format("{:.5f}"), width="stretch")
        plot = result.coefficients.drop(index="alpha").reset_index()
        plot["upper"] = plot["ci_95_high"] - plot["coefficient"]
        plot["lower"] = plot["coefficient"] - plot["ci_95_low"]
        fig = px.scatter(
            plot,
            x="factor",
            y="coefficient",
            error_y="upper",
            error_y_minus="lower",
            title="Exposições e intervalos de confiança de 95% (HAC)",
        )
        fig.add_hline(y=0, line_dash="dash")
        st.plotly_chart(fig, width="stretch")
        st.caption(
            "Alpha e retornos em decimal mensal. Betas são adimensionais. "
            "p-valores usam inferência t com covariância HAC; não implicam causalidade."
        )
    with tabs[1]:
        comparison = pd.concat([result.data["excess_return"], result.fitted], axis=1)
        st.plotly_chart(
            px.line(comparison, title="Retorno excedente observado e ajustado"), width="stretch"
        )
        left, right = st.columns(2)
        left.plotly_chart(px.line(result.residuals, title="Resíduos mensais"), width="stretch")
        right.plotly_chart(
            px.histogram(
                result.residuals.to_frame(),
                x="residual",
                nbins=30,
                title="Distribuição dos resíduos",
            ),
            width="stretch",
        )
        st.dataframe(pd.Series(result.diagnostics, name="valor").to_frame())
        st.caption(
            "Jarque–Bera: normalidade; Breusch–Pagan: homocedasticidade; "
            "Ljung–Box: ausência de autocorrelação. p pequeno rejeita a hipótese nula. "
            "Durbin–Watson próximo de 2 é compatível com baixa autocorrelação de ordem 1."
        )
    with tabs[2]:
        if result.rolling.empty:
            st.info("Amostra menor que a janela móvel selecionada.")
        else:
            st.plotly_chart(
                px.line(
                    result.rolling.drop(columns="alpha"),
                    title=f"Betas móveis · janela de {used_window} meses",
                ),
                width="stretch",
            )
            st.caption(
                "Estimativas OLS por janela, sem intervalos de confiança; não são previsões."
            )
    with tabs[3]:
        observations = result.data.join(result.fitted).join(result.residuals)
        st.dataframe(observations, width="stretch")
        for filename, frame in [
            ("coefficients.csv", result.coefficients),
            ("observations.csv", observations),
            ("rolling.csv", result.rolling),
        ]:
            st.download_button(
                f"Baixar {filename}",
                frame.to_csv().encode("utf-8"),
                file_name=filename,
                mime="text/csv",
            )

st.divider()
st.caption(
    "Uso educacional e analítico, não recomendação de investimento. "
    "Fatores: Kenneth R. French Data Library (EUA). Preços: Yahoo Finance via yfinance. "
    "Não aplique os fatores americanos diretamente a retornos em BRL."
)
