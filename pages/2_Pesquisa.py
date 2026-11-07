"""Workspace multivariado: amostra comum entre todos os ativos e modelos."""

import io
import logging
from datetime import date

import numpy as np
import pandas as pd
import plotly.express as px
import streamlit as st

from factorlab.data import demo_data, load_factors, load_prices, month_index, monthly_returns
from factorlab.forecast import forecast_walk_forward
from factorlab.operations import classify_error
from factorlab.provenance import cache_status, manifest
from factorlab.providers import BR_MODELS, load_nefin
from factorlab.quality import audit_panel, calendar_audit, source_health
from factorlab.report import export_bundle, html_report, pdf_report
from factorlab.research import (
    compare,
    parse_weights,
    portfolio_returns,
    validate_panel,
    walk_forward,
)
from factorlab.research_ui import render_research_tools
from factorlab.security import workspace_root
from factorlab.ui import context_strip, setup_terminal, welcome_cards
from ui.components import (
    footer,
    format_chart,
    percent,
    sidebar_header,
    sidebar_section,
    styled_table,
)
from ui.theme import DIVERGING

st.set_page_config(page_title="FactorLab | Portfolio Research", page_icon="F", layout="wide")
setup_terminal("Pesquisa de carteiras / Múltiplos ativos")
st.title("Pesquisa de carteiras")
st.caption("Amostra mensal comum para todos os ativos e modelos selecionados.")

with st.sidebar:
    sidebar_header("Pesquisa de carteiras", "Universo, alocação e modelos")
    sidebar_section("01", "Mercado e dados")
    market = st.selectbox("Mercado / moeda", ["EUA / USD", "Brasil / BRL"])
    source = st.radio("Dados", ["Demonstração", "Yahoo Finance", "CSV de retornos"], index=1)
    tickers_text = st.text_input("Ativos separados por vírgula", "AAPL, MSFT, SPY, IWM")
    benchmark = st.text_input("Benchmark", "SPY").strip().upper()
    models = st.multiselect(
        "Modelos",
        BR_MODELS if market.startswith("Brasil") else ["CAPM", "FF3", "FF5", "CARHART4", "FF6"],
        default=["CAPM", "FF3"],
    )
    sidebar_section("02", "Período e arquivo")
    start = st.date_input("Início", date(2015, 1, 1), min_value=date(1926, 1, 1))
    end = st.date_input("Fim exclusivo", date.today(), min_value=date(1926, 1, 1))
    uploaded = st.file_uploader("CSV: date,AAPL,MSFT,SPY,... · decimais", type="csv")
    sidebar_section("03", "Construção da carteira")
    weights_text = st.text_area(
        "Carteira opcional · um ativo:peso por linha", "AAPL: 30%\nMSFT: 30%\nSPY: 40%"
    )
    policy = st.selectbox(
        "Política da carteira",
        ["monthly", "buy_hold"],
        format_func=lambda v: {
            "monthly": "Rebalanceamento mensal",
            "buy_hold": "Buy-and-hold · pesos variáveis",
        }[v],
    )
    sidebar_section("04", "Parâmetros de pesquisa")
    lags = st.slider("Defasagens HAC", 0, 12, 3)
    window = st.slider("Janela de estabilidade / treino", 24, 120, 60, step=12)
    forecast_lag = st.slider("Defasagem dos fatores para previsão (meses)", 1, 6, 2)
    refresh = st.checkbox("Atualizar fatores ao executar", value=False)
    st.divider()
    sidebar_section("05", "Validação e execução")
    audit_only = st.button("Inspecionar dados antes da regressão", width="stretch")
    quality_confirmed = st.checkbox("Confirmo revisar a qualidade dos dados", value=False)
    run = st.button("Executar pesquisa", type="primary", width="stretch")

if st.button("Atualizar fatores agora"):
    try:
        if market.startswith("Brasil"):
            load_nefin(refresh=True)
        else:
            for model in models:
                load_factors(model, refresh=True)
        st.cache_data.clear()
        st.success("Fatores atualizados. Execute novamente a pesquisa para usar a nova versão.")
    except Exception as exc:
        st.error(str(exc))

status = cache_status()
with st.expander("Qualidade e atualização das fontes"):
    if status:
        styled_table(pd.DataFrame(status), width="stretch")
        if any(row["stale"] for row in status):
            st.warning(
                "Há cache com 7 dias ou mais. Atualize os fatores antes de uma nova análise."
            )
    else:
        st.info("Nenhum download de fatores registrado neste ambiente.")

if "quality_preview" in st.session_state:
    with st.expander("DATA QUALITY / Auditoria pré-regressão", expanded=True):
        for title, frame in st.session_state["quality_preview"].items():
            st.caption(title)
            styled_table(frame, width="stretch")

if run or audit_only:
    st.session_state.pop("study", None)
    try:
        if start >= end or not models:
            raise ValueError("Selecione modelos e um intervalo válido.")
        tickers = list(
            dict.fromkeys(t.strip().upper() for t in tickers_text.split(",") if t.strip())
        )
        if not tickers or not benchmark:
            raise ValueError("Informe ativos e benchmark.")
        if "Carteira" in tickers:
            raise ValueError("Nome Carteira é reservado.")
        all_tickers = list(dict.fromkeys([*tickers, benchmark]))
        if len(all_tickers) > 12:
            raise ValueError("Limite operacional: 12 ativos incluindo benchmark.")
        if uploaded is not None and uploaded.size > 10_000_000:
            raise ValueError("Upload excede 10 MB.")
        progress = st.progress(0.05, text="01 / Aquisição e origem dos dados")
        calendar_frames = {}
        with st.spinner("Executando pesquisa…"):
            is_br = market.startswith("Brasil")
            if source == "Demonstração":
                base, factors = demo_data()
                rng = np.random.default_rng(73)
                panel = pd.DataFrame(
                    {
                        t: base * (0.7 + 0.2 * i) + rng.normal(0, 0.01, len(base))
                        for i, t in enumerate(all_tickers)
                    }
                )
                factor_sets = {m: factors.copy() for m in models}
            else:
                if source == "Yahoo Finance":
                    if is_br and any(not t.endswith(".SA") for t in all_tickers):
                        raise ValueError(
                            "Brasil: use ativos e ETF benchmark em BRL com sufixo .SA (ex.: BOVA11.SA)."
                        )
                    if not is_br and any(t.endswith(".SA") for t in all_tickers):
                        raise ValueError("Ativos .SA exigem fatores Brasil / BRL.")
                    series = {}
                    for i, t in enumerate(all_tickers):
                        prices = load_prices(t, str(start), str(end))
                        calendar_frames[t] = calendar_audit(prices, "BMF" if is_br else "NYSE")
                        series[t] = monthly_returns(prices, "BMF" if is_br else "NYSE")
                        progress.progress(
                            0.1 + 0.3 * (i + 1) / len(all_tickers), text=f"01 / Recebido {t}"
                        )
                    panel = pd.concat(series, axis=1, join="outer")
                    panel.attrs["provenance"] = {
                        t: s.attrs.get("provenance", {}) for t, s in series.items()
                    }
                else:
                    if uploaded is None:
                        raise ValueError("Envie CSV com date e uma coluna por ativo.")
                    from factorlab.provenance import snapshot

                    raw_record = snapshot(
                        uploaded.getvalue(), "Uploaded returns CSV", workspace_root()
                    )
                    frame = pd.read_csv(io.BytesIO(uploaded.getvalue()))
                    frame.index = month_index(frame.pop("date"))
                    frame.columns = frame.columns.str.strip().str.upper()
                    panel = frame[all_tickers].astype(float)
                    panel = panel.loc[
                        (panel.index >= pd.Timestamp(start)) & (panel.index < pd.Timestamp(end))
                    ]
                    panel.attrs["provenance"] = raw_record
                factor_sets = {
                    m: load_nefin(refresh=refresh) if is_br else load_factors(m, refresh=refresh)
                    for m in models
                }
            progress.progress(0.45, text="02 / Auditoria de qualidade antes dos cálculos")
            quality, extremes, common = audit_panel(
                panel, factor_sets, "BRL" if is_br else "USD", source
            )
            sources = source_health(
                {
                    **panel.attrs.get("provenance", {}),
                    **{m: f.attrs.get("provenance", {}) for m, f in factor_sets.items()},
                }
            )
            preview = {
                "Histórico, faltantes e amostra descartada": quality,
                "Retornos extremos |retorno| > 25% (revisar, não corrigir)": extremes,
                "Origem e atualização (não é teste de disponibilidade em tempo real)": sources,
            }
            preview.update({f"Sessões ausentes {t}": f for t, f in calendar_frames.items()})
            st.session_state["quality_preview"] = preview
            if audit_only or (source != "Demonstração" and not quality_confirmed):
                for title, frame in preview.items():
                    st.caption(title)
                    styled_table(frame, width="stretch")
                st.info(
                    "Revise as observações. Confirme a revisão e clique em Executar pesquisa. Nenhum valor foi corrigido."
                )
                progress.empty()
                st.stop()
            panel = validate_panel(panel)
            if len(panel) > 600:
                raise ValueError("Limite operacional: 600 meses por estudo.")
            progress.progress(0.6, text="03 / Estimação em amostra comum")
            # Constrói a carteira só depois de encontrar a mesma amostra para todos.
            preliminary = compare(panel, factor_sets, benchmark, lags, window)
            panel = preliminary.returns
            extras = {f"quality_{name}": frame for name, frame in preview.items()}
            for job_key in ["bootstrap_job", "execution_job"]:
                job = st.session_state.pop(job_key, None)
                if job is not None:
                    job.cancel()
            if weights_text.strip():
                weights = parse_weights(weights_text)
                portfolio, history = portfolio_returns(panel, weights, policy)
                panel["Carteira"] = portfolio
                extras["portfolio_weights_beginning_of_month"] = history
            else:
                weights = {}
            study = compare(panel, factor_sets, benchmark, lags, window)
            progress.progress(0.75, text="04 / Avaliação temporal e previsões")
            oos = {}
            for (asset, model), result in study.results.items():
                if len(result.data) > window:
                    oos[asset, model] = walk_forward(
                        study.returns[asset],
                        factor_sets[model].loc[study.returns.index],
                        model,
                        window,
                    )
                    extras[f"walk_forward_{asset}_{model}"] = oos[asset, model]
            for (asset, model), result in study.results.items():
                if len(result.data) > window + forecast_lag:
                    extras[f"forecast_{asset}_{model}"] = forecast_walk_forward(
                        study.returns[asset],
                        factor_sets[model].loc[study.returns.index],
                        model,
                        window,
                        forecast_lag,
                    )
            metadata = manifest(
                {
                    "market": market,
                    "source": source,
                    "synthetic": source == "Demonstração",
                    "tickers": all_tickers,
                    "benchmark": benchmark,
                    "models": models,
                    "start_requested": str(start),
                    "end_exclusive": str(end),
                    "weights": weights,
                    "policy": policy,
                    "hac_lags": lags,
                    "window": window,
                    "forecast_publication_lag": forecast_lag,
                    "calendar": "BMF" if is_br else "NYSE",
                },
                {"returns": study.returns, **{f"factors_{m}": f for m, f in factor_sets.items()}},
                root=workspace_root(),
            )
            metadata["data_stale"] = bool(
                not sources.empty and sources.status.eq("desatualizada").any()
            )
            metadata["quality_policy"] = (
                "Auditoria sem correção automática; extremos acima de 25% para revisão."
            )
            progress.progress(1.0, text="05 / Pesquisa concluída")
            st.session_state["study"] = study, metadata, extras, oos
    except Exception as exc:
        logging.getLogger(__name__).exception("Falha na pesquisa")
        category, hint = classify_error(exc)
        st.session_state["quality_preview"] = {
            "Falha de origem ou processamento": pd.DataFrame(
                [{"status": "erro", "category": category, "message": str(exc)}]
            )
        }
        st.error(f"[{category}] Pesquisa não concluída: {exc}. {hint}")

if "study" not in st.session_state:
    context_strip(
        [
            ("AMBIENTE", "Pesquisa de carteiras"),
            ("ALOCAÇÃO", "Sem posições vendidas"),
            ("AVALIAÇÃO", "Janelas temporais"),
            ("EXPORTAÇÃO", "HTML / PDF / ZIP"),
        ]
    )
    welcome_cards()

if "study" in st.session_state:
    study, metadata, extras, oos = st.session_state["study"]
    context_strip(
        [
            ("UNIVERSO", metadata["parameters"]["market"]),
            ("BENCHMARK", study.benchmark),
            ("AMOSTRA", f"{len(study.returns)} meses"),
            ("POLÍTICA", metadata["parameters"]["policy"]),
        ]
    )
    st.caption("Resultados da última execução; alterações nos controles exigem nova execução.")
    if metadata["parameters"]["synthetic"]:
        st.warning(
            "DADOS SINTÉTICOS · não representam os ativos nomeados. Datas selecionadas ignoradas."
        )
    st.write(
        f"Amostra: {study.returns.index.min():%Y-%m} — {study.returns.index.max():%Y-%m} · {len(study.returns)} meses"
    )
    workspace = st.radio(
        "Estação de trabalho",
        ["VISÃO GERAL", "RISCO E CARTEIRA", "OPERAÇÕES", "RELATÓRIOS"],
        horizontal=True,
        key="workspace_nav",
    )
    from contextlib import nullcontext

    tabs = [nullcontext() for _ in range(5)]
    if workspace == "VISÃO GERAL":
        tabs = st.tabs(
            [
                "Comparação",
                "Carteira e benchmark",
                "Modelos e estabilidade",
                "Walk-forward",
                "Relatório e exportação",
            ]
        )
    if workspace == "VISÃO GERAL":
        with tabs[0]:
            styled_table(study.summary, width="stretch")
            selected = st.selectbox(
                "Modelo do heatmap", list(study.summary.index.get_level_values("model").unique())
            )
            betas = study.summary.xs(selected, level="model").filter(regex="^beta_")
            st.plotly_chart(
                px.imshow(
                    betas,
                    text_auto=".2f",
                    color_continuous_scale=DIVERGING,
                    color_continuous_midpoint=0,
                    title="Exposições aos fatores",
                ),
                width="stretch",
            )
    if workspace == "VISÃO GERAL":
        with tabs[1]:
            st.plotly_chart(
                format_chart(
                    px.line((1 + study.returns).cumprod(), title="Evolução do patrimônio"), "wealth"
                ),
                width="stretch",
            )
            st.caption(
                f"Benchmark: {study.benchmark}. Active return = 12 × média mensal da diferença; tracking error = desvio da diferença × √12."
            )
            if extras.get("portfolio_weights_beginning_of_month") is not None:
                styled_table(extras["portfolio_weights_beginning_of_month"], width="stretch")
                st.caption(
                    f"Política: {metadata['parameters']['policy']}. Pesos no início do mês. Sem custos, impostos ou aportes."
                )
    if workspace == "VISÃO GERAL":
        with tabs[2]:
            st.info(
                "FF3/Carhart usam SMB da família FF3; FF5/FF6 usam SMB da família FF5. Mesma amostra não torna os modelos estritamente aninhados."
            )
            key = st.selectbox(
                "Ativo/modelo para estabilidade",
                list(study.results),
                format_func=lambda x: " · ".join(x),
            )
            rolling = study.results[key].rolling
            if not rolling.empty:
                st.plotly_chart(
                    px.line(rolling.drop(columns="alpha"), title="Betas móveis"), width="stretch"
                )
            st.caption(
                "rolling_std_* na tabela: desvio dos coeficientes entre janelas sobrepostas (descritivo, não teste formal). AIC/BIC: critérios gaussianos convencionais."
            )
    if workspace == "VISÃO GERAL":
        with tabs[3]:
            st.warning(
                "Fatores do mês de teste são realizados: avaliação explicativa retrospectiva, NÃO previsão negociável."
            )
            if oos:
                key = st.selectbox("Walk-forward", list(oos), format_func=lambda x: " · ".join(x))
                frame = oos[key]
                st.metric("RMSE fora da amostra", percent(np.sqrt(np.mean(frame.error**2)), 3))
                st.plotly_chart(
                    format_chart(px.line(frame[["actual_excess", "explained_excess"]]), "percent"),
                    width="stretch",
                )
                styled_table(frame, width="stretch")
            else:
                st.info("Amostra insuficiente: reduza a janela ou aumente o intervalo.")
            forecasts = {k: v for k, v in extras.items() if k.startswith("forecast_")}
            st.subheader("Previsão ex ante com fatores defasados")
            st.caption(
                "Somente informações de meses anteriores. A defasagem é conservadora, mas não verifica datas históricas de publicação/revisão; não certifica backtest investível."
            )
            if forecasts:
                chosen = st.selectbox("Previsão", list(forecasts))
                predicted = forecasts[chosen]
                st.metric("RMSE previsão", percent(np.sqrt(np.mean(predicted.error**2)), 3))
                st.metric(
                    "RMSE referência: média histórica",
                    percent(np.sqrt(np.mean(predicted.baseline_error**2)), 3),
                )
                st.plotly_chart(
                    format_chart(
                        px.line(
                            predicted[
                                ["actual_return", "predicted_return", "historical_mean_forecast"]
                            ]
                        ),
                        "percent",
                    ),
                    width="stretch",
                )
                styled_table(predicted, width="stretch")
            else:
                st.info("Amostra insuficiente para previsão defasada.")
    if workspace == "RISCO E CARTEIRA":
        st.subheader("Risco e carteira")
        render_research_tools(study, metadata, extras)
    from factorlab.advanced_ui import render_advanced

    if workspace == "OPERAÇÕES":
        render_advanced(study, metadata, extras)
    if workspace == "RELATÓRIOS":
        selected_extras = st.multiselect(
            "Conteúdo do relatório", list(extras), default=list(extras)
        )
        report_extras = {name: extras[name] for name in selected_extras}
        st.download_button(
            "Baixar relatório PDF",
            pdf_report(study, metadata, report_extras),
            "report.pdf",
            "application/pdf",
        )
        st.download_button(
            "Baixar relatório HTML",
            html_report(study, metadata, report_extras).encode(),
            "report.html",
            "text/html",
        )
        st.download_button(
            "Baixar pacote consolidado ZIP",
            export_bundle(study, metadata, report_extras),
            "factorlab.zip",
            "application/zip",
        )
        st.download_button(
            "Baixar tabela consolidada CSV",
            study.summary.to_csv().encode(),
            "summary.csv",
            "text/csv",
        )
        st.json(metadata)
        st.caption("PDF gerado nativamente no servidor, sem navegador ou serviço externo.")

footer()
st.caption(
    "NEFIN (Brasil): fatores mensais value-weighted em BRL, CAPM/FF3/Carhart4; não oferece RMW/CMA neste dataset. Kenneth French (EUA): USD. Calendários NYSE/BMF via pandas-market-calendars."
)
