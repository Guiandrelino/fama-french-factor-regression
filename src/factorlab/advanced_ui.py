"""Workspaces de operação e pesquisa com tarefas limitadas por sessão."""

import plotly.express as px
import streamlit as st

from factorlab.alerts import exposure_alerts
from factorlab.evaluation import performance_metrics, rolling_allocation
from factorlab.operations import EXECUTOR
from factorlab.security import backup_database, purge_snapshots, restore_database, workspace_root
from factorlab.storage import AnalysisStore
from factorlab.uncertainty import allocation_sensitivity, bootstrap_risk, bootstrap_weights


def render_advanced(study, metadata, extras):
    tabs = st.tabs(["EXECUTION LAB", "UNCERTAINTY", "EXPOSURE MONITOR", "WORKSPACE ADMIN"])
    with tabs[0]:
        assets = [a for a in study.returns if a not in {"Carteira", study.benchmark}]
        if not assets:
            assets = [study.benchmark]
        policy = st.selectbox("Rebalanceamento", ["monthly", "quarterly", "bands"])
        window = st.slider("Treino rolling", 24, 120, 60, 12)
        cost = st.number_input("Custo em bps por turnover one-way", 0.0, 1000.0, 10.0)
        band = st.slider("Banda de desvio de peso", 0.01, 0.3, 0.05, 0.01)
        cap = st.slider("Limite individual", 0.1, 1.0, 0.6, 0.05)
        group_text = st.text_area("Grupos (JSON ativo:grupo)", value="{}")
        caps_text = st.text_area("Limites de grupo (JSON grupo:peso)", value="{}")
        if st.button("Executar avaliação rolling"):
            import json

            try:
                result, weights = rolling_allocation(
                    study.returns[assets],
                    window,
                    policy,
                    cost,
                    band,
                    cap,
                    groups=json.loads(group_text),
                    group_caps=json.loads(caps_text),
                )
                comparison = result[["gross", "net"]].copy()
                comparison["benchmark"] = study.returns.loc[result.index, study.benchmark]
                comparison["equal_weight_gross"] = study.returns.loc[result.index, assets].mean(
                    axis=1
                )
                extras["execution_returns"] = comparison
                extras["execution_cost_turnover"] = result[["cost", "turnover"]]
                extras["execution_metrics"] = performance_metrics(comparison)
                extras["execution_weights"] = weights
            except (ValueError, KeyError) as exc:
                st.error(str(exc))
        if "execution_returns" in extras:
            st.plotly_chart(px.line((1 + extras["execution_returns"]).cumprod()), width="stretch")
            st.dataframe(extras["execution_metrics"], width="stretch")
            st.dataframe(extras["execution_cost_turnover"], width="stretch")
        st.caption(
            "Janelas sucessivas sem retornos futuros. Referências benchmark/equiponderada são brutas; net desconta custos da estratégia. Sharpe usa RF=0, não é excesso sobre taxa livre de risco. Bandas podem violar temporariamente limites até o próximo rebalanceamento."
        )
    with tabs[1]:
        key = st.selectbox(
            "Modelo para bootstrap", list(study.results), format_func=lambda x: " / ".join(x)
        )
        reps = st.slider("Réplicas", 20, 200, 40, 20)
        block = st.slider("Comprimento de bloco mensal", 1, 12, 6)
        running = st.session_state.get("bootstrap_job")
        if st.button(
            "Calcular incerteza em background", disabled=running is not None and not running.done()
        ):
            result = study.results[key]
            panel = study.returns.drop(columns="Carteira", errors="ignore").copy()

            def work():
                _, risk_ci = bootstrap_risk(result, reps, block)
                draws, weight_ci = bootstrap_weights(panel, reps, block, max_weight=1.0)
                return risk_ci, draws, weight_ci, allocation_sensitivity(panel, max_weight=1.0)

            st.session_state["bootstrap_job"] = EXECUTOR.submit(work)
        job = st.session_state.get("bootstrap_job")
        if job is not None:
            if st.button("Cancelar tarefa pendente"):
                cancelled = job.cancel()
                st.info(
                    "Tarefa cancelada." if cancelled else "Tarefa já em execução; aguarde terminar."
                )
            if job.done():
                try:
                    ci, draws, weight_ci, sensitivity = job.result()
                    extras["bootstrap_risk_ci"] = ci
                    extras["bootstrap_weight_ci"] = weight_ci
                    extras["allocation_sensitivity"] = sensitivity
                    st.dataframe(ci, width="stretch")
                    st.plotly_chart(px.box(draws), width="stretch")
                    st.dataframe(weight_ci, width="stretch")
                    st.dataframe(sensitivity, width="stretch")
                except Exception as exc:
                    st.error(str(exc))
            else:
                st.info("Tarefa em processamento. Clique em Atualizar tarefa para consultar.")
                st.button("Atualizar tarefa")
        st.caption(
            "Moving-block bootstrap com seed fixa; intervalos percentis descritivos, sem garantia sob mudanças de regime. Alocação bootstrap long-only com máximo 100%; não representa automaticamente os limites de outra otimização."
        )
    with tabs[2]:
        store = AnalysisStore(workspace_root() / "analyses.sqlite")
        saved = store.list()
        if not saved.empty:
            selected = st.selectbox("Referência dos alertas", saved.id.tolist())
            limit = st.number_input("Limite beta mercado", value=1.2)
            growth = st.slider("Aumento relativo de vol. residual", 0.05, 1.0, 0.25, 0.05)
            old = store.load(selected)
            current_weights = extras.get("portfolio_weights_beginning_of_month")
            weights = current_weights.iloc[-1].to_dict() if current_weights is not None else None
            alerts = exposure_alerts(
                study.summary,
                old["summary"],
                limit,
                growth,
                weights,
                metadata["parameters"].get("weights"),
                stale=metadata.get("data_stale", False),
            )
            extras["exposure_alerts"] = alerts
            st.dataframe(alerts, width="stretch")
            st.caption(
                "Comparação descritiva. Verifique moeda, amostra e modelo da referência. Nenhum alerta dispara ordem."
            )
        else:
            st.info("Salve uma análise para definir a referência.")
    with tabs[3]:
        root = workspace_root()
        store = AnalysisStore(root / "analyses.sqlite")
        st.download_button(
            "Backup do banco local", backup_database(store.path), "analyses.backup.sqlite"
        )
        uploaded = st.file_uploader("Restaurar backup SQLite", type="sqlite")
        confirm = st.checkbox("Confirmo substituir meu banco atual")
        if st.button("Restaurar banco", disabled=not confirm or uploaded is None):
            try:
                backup_database(store.path)
                restore_database(store.path, uploaded.getvalue())
                st.success("Banco restaurado; backup anterior mantido no workspace.")
            except ValueError as exc:
                st.error(str(exc))
        days = st.number_input("Retenção de snapshots (dias)", min_value=1, value=30)
        if st.button("Excluir snapshots anteriores à retenção"):
            st.success(
                f"{purge_snapshots(root, int(days))} snapshots removidos. Manifestos antigos podem perder evidências."
            )
        st.caption(
            "Backup contém dados privados; guarde com segurança. Retenção é explícita, não automática. Publicação exige HTTPS e autenticação por ambiente."
        )
