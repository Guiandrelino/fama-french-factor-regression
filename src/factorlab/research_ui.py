"""Ferramentas adicionais do workspace, na ordem do fluxo de pesquisa."""

import numpy as np
import pandas as pd
import plotly.express as px
import streamlit as st

from factorlab.diagnostics import advanced_diagnostics, hac_sensitivity
from factorlab.optimization import holdout_optimization
from factorlab.regression import fit_model
from factorlab.risk import historical_stress, risk_decomposition, stress_scenario
from factorlab.storage import AnalysisStore, compare_saved


def render_research_tools(study, metadata, extras):
    tabs = st.tabs(
        [
            "01 · Risco",
            "02 · Estresse",
            "03 · Análises salvas",
            "04 · Diagnóstico avançado",
            "05 · Otimização",
        ]
    )
    keys = list(study.results)
    with tabs[0]:
        key = st.selectbox("Decomposição de risco", keys, format_func=lambda x: " / ".join(x))
        result = study.results[key]
        table, metrics = risk_decomposition(result)
        cols = st.columns(3)
        for col, (name, value) in zip(cols, metrics.items(), strict=True):
            col.metric(name.replace("_", " "), f"{value:.2%}")
        st.plotly_chart(
            px.bar(
                table.reset_index(),
                x="factor",
                y="variance_annual",
                title="Contribuições à variância anualizada",
            ),
            width="stretch",
        )
        st.dataframe(table, width="stretch")
        st.caption(
            "Euler: beta × (Cov(fatores) × beta), mais variância residual. Inclui covariâncias; contribuições negativas são possíveis. Anualização ×12 pressupõe convenção sem autocovariâncias. Risco ex post, não previsão."
        )
        extras[f"risk_contributions_{key[0]}_{key[1]}"] = table
    with tabs[1]:
        key = st.selectbox("Ativo/modelo do cenário", keys, format_func=lambda x: " / ".join(x))
        result = study.results[key]
        names = result.coefficients.index.drop("alpha")
        shocks = {}
        for factor in names:
            shocks[factor] = (
                st.number_input(
                    f"{factor} · retorno do fator (%)",
                    value=-10.0 if factor == "Mkt-RF" else 0.0,
                    step=1.0,
                    key=f"shock_{key}_{factor}",
                )
                / 100
            )
        table, impact = stress_scenario(result, shocks)
        st.metric("Impacto sistemático mensal", f"{impact:.2%}")
        st.dataframe(table, width="stretch")
        extras[f"custom_stress_{key[0]}_{key[1]}"] = table
        st.caption(
            "Retorno excedente condicionado aos choques. Alpha, RF, resíduos, não linearidades e custos não incluídos; não é VaR nem perda máxima."
        )
        historical = st.selectbox("Cenário observado", ["Março 2020", "Ano 2022", "Toda a amostra"])
        start, end = {
            "Março 2020": ("2020-03", "2020-03"),
            "Ano 2022": ("2022-01", "2022-12"),
            "Toda a amostra": (
                str(result.data.index.min().date()),
                str(result.data.index.max().date()),
            ),
        }[historical]
        try:
            observed = historical_stress(result, start, end)
            st.dataframe(observed, width="stretch")
            extras[f"historical_stress_{key[0]}_{key[1]}_{historical}"] = observed.to_frame()
        except ValueError as exc:
            st.info(str(exc))
        st.caption(
            "Reaplicação de fatores observados aos betas da amostra atual: não usa as posições nem betas históricos da carteira."
        )
    with tabs[2]:
        store = AnalysisStore()
        name = st.text_input("Nome da análise", "Minha análise")
        if st.button("Salvar análise local"):
            try:
                identifier = store.save(name, study, metadata)
                st.success(f"Análise salva: #{identifier}")
            except ValueError as exc:
                st.error(str(exc))
        saved = store.list()
        st.caption(
            "SQLite local compartilhado entre sessões deste servidor. Não armazene carteiras privadas em um deploy público sem autenticação. Excluir análise não remove snapshots de origem."
        )
        if not saved.empty:
            st.dataframe(saved, width="stretch")
            ids = saved.id.tolist()
            selected = st.selectbox("Análise armazenada", ids)
            loaded = store.load(selected)
            st.dataframe(loaded["summary"], width="stretch")
            st.download_button(
                "Exportar análise salva",
                loaded["summary"].to_csv().encode(),
                "saved-analysis.csv",
                "text/csv",
            )
            if len(ids) > 1:
                other = st.selectbox("Comparar com análise", ids, index=1)
                st.json(
                    {
                        "primeira": loaded["metadata"]["parameters"],
                        "segunda": store.load(other)["metadata"]["parameters"],
                    }
                )
                try:
                    st.dataframe(compare_saved(loaded, store.load(other)), width="stretch")
                except ValueError as exc:
                    st.info(str(exc))
                st.caption(
                    "Diferença = segunda − primeira. Períodos, moedas e fontes podem diferir: não interprete como teste estatístico de melhora."
                )
            confirm = st.checkbox("Confirmo excluir a análise selecionada")
            if st.button("Excluir análise", disabled=not confirm):
                store.delete(selected)
                st.rerun()
    with tabs[3]:
        key = st.selectbox("Diagnóstico do modelo", keys, format_func=lambda x: " / ".join(x))
        result = study.results[key]
        correlation, vif, influence = advanced_diagnostics(result)
        st.plotly_chart(
            px.imshow(
                correlation, text_auto=".2f", zmin=-1, zmax=1, color_continuous_scale="RdBu_r"
            ),
            width="stretch",
        )
        st.dataframe(vif.to_frame(), width="stretch")
        st.dataframe(influence.sort_values("cooks_distance", ascending=False), width="stretch")
        sensitivity = hac_sensitivity(result)
        st.dataframe(sensitivity, width="stretch")
        st.caption(
            "VIF alto sugere colinearidade. Cook > 4/n é triagem heurística, não motivo automático para excluir observações. Sensibilidade HAC altera inferência, não coeficientes OLS. Diagnósticos de influência são OLS convencionais."
        )
        extras[f"influence_{key[0]}_{key[1]}"] = influence
        extras[f"hac_sensitivity_{key[0]}_{key[1]}"] = sensitivity
    with tabs[4]:
        candidates = [c for c in study.returns if c not in {"Carteira", study.benchmark}]
        if not candidates:
            candidates = [c for c in study.returns if c != "Carteira"]
        assets = st.multiselect(
            "Ativos elegíveis",
            list(study.returns.columns.drop("Carteira", errors="ignore")),
            default=candidates,
        )
        model = st.selectbox("Modelo dos limites de beta", list(dict.fromkeys(m for _, m in keys)))
        max_weight = st.slider("Peso máximo por ativo", 0.1, 1.0, 0.6, 0.05)
        ridge = st.slider("Regularização da covariância", 0.0, 1.0, 0.1, 0.05)
        train = st.number_input(
            "Meses de treino", min_value=24, value=max(24, int(len(study.returns) * 0.7)), step=1
        )
        limit_beta = st.checkbox("Limitar beta de mercado")
        lower = st.number_input("Beta mercado mínimo", value=0.0)
        upper = st.number_input("Beta mercado máximo", value=1.5)
        if st.button("Otimizar e avaliar fora da amostra"):
            try:
                panel = study.returns[assets]
                # Betas de restrição estimados SOMENTE no treino, nunca no período de teste.
                exposures = pd.DataFrame(
                    {
                        a: fit_model(
                            panel[a].iloc[: int(train)],
                            study.results[a, model].data.iloc[: int(train)],
                            model,
                        ).coefficients.coefficient.drop("alpha")
                        for a in assets
                    }
                ).T
                bounds = {"Mkt-RF": (lower, upper)} if limit_beta else None
                weights, vol, performance = holdout_optimization(
                    panel, int(train), max_weight, ridge, exposures, bounds
                )
                st.dataframe(weights.to_frame(), width="stretch")
                st.metric("Volatilidade estimada no treino", f"{vol:.2%}")
                st.plotly_chart(
                    px.line(
                        (1 + performance).cumprod(),
                        title="Avaliação fora da amostra · pesos mensais fixos",
                    ),
                    width="stretch",
                )
                st.dataframe(performance.std().mul(np.sqrt(12)).rename("vol_annual").to_frame())
                st.download_button(
                    "Baixar pesos otimizados",
                    weights.to_csv().encode(),
                    "optimized-weights.csv",
                    "text/csv",
                )
                st.download_button(
                    "Baixar avaliação",
                    performance.to_csv().encode(),
                    "optimization-holdout.csv",
                    "text/csv",
                )
            except (ValueError, KeyError) as exc:
                st.error(str(exc))
        st.caption(
            "Mínima variância regularizada, long-only, soma=100%. Pesos e betas são estimados apenas no treino. Holdout não entra na otimização, mas a seleção prévia de ativos pode introduzir viés. Sem custos/impostos. Não é recomendação de investimento."
        )
