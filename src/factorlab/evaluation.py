"""Simulação mensal com custos, drift e decisões sem acesso a retornos futuros."""

import numpy as np
import pandas as pd

from factorlab.optimization import optimize_portfolio
from factorlab.research import validate_panel


def performance_metrics(returns, rf=None):
    wealth = (1 + returns).cumprod()
    drawdown = wealth / wealth.cummax().clip(lower=1) - 1
    volatility = returns.std(ddof=1) * np.sqrt(12)
    if rf is not None:
        risk_free = rf.reindex(returns.index)
        if risk_free.isna().any():
            raise ValueError("RF ausente na avaliação.")
        excess = returns.sub(risk_free, axis=0)
    else:
        excess = returns
    return pd.DataFrame(
        {
            "cumulative_return": wealth.iloc[-1] - 1,
            "annualized_return": wealth.iloc[-1] ** (12 / len(returns)) - 1,
            "vol_annual": volatility,
            "max_drawdown": drawdown.min(),
            ("sharpe_excess" if rf is not None else "sharpe_rf_zero"): excess.mean()
            * 12
            / (excess.std(ddof=1) * np.sqrt(12)).replace(0, np.nan),
        }
    )


def rolling_allocation(
    panel,
    train_window=60,
    policy="monthly",
    cost_bps=10,
    band=0.05,
    max_weight=0.6,
    ridge=0.1,
    groups=None,
    group_caps=None,
):
    panel = validate_panel(panel)
    if (
        train_window < 24
        or len(panel) - train_window < 12
        or cost_bps < 0
        or policy not in {"monthly", "quarterly", "bands"}
    ):
        raise ValueError("Configuração inválida; exige 24 meses de treino e 12 de teste.")
    previous = None
    rows, weights = [], []
    for stop in range(train_window, len(panel)):
        target, _ = optimize_portfolio(
            panel.iloc[stop - train_window : stop],
            max_weight,
            ridge,
            groups=groups,
            group_caps=group_caps,
        )
        rebalance = (
            previous is None
            or policy == "monthly"
            or (policy == "quarterly" and (stop - train_window) % 3 == 0)
        )
        if policy == "bands" and previous is not None:
            rebalance = bool((target - previous).abs().max() > band)
        current = target if rebalance else previous
        # Turnover one-way = meia soma das compras/vendas; entrada inicial = 100%.
        turnover = 1.0 if previous is None else float((current - previous).abs().sum() / 2)
        cost = turnover * cost_bps / 10000
        gross = float(panel.iloc[stop] @ current)
        net = (1 - cost) * (1 + gross) - 1
        if gross <= -1:
            raise ValueError("Perda total: pesos futuros indefinidos.")
        previous = current * (1 + panel.iloc[stop]) / (1 + gross)
        weights.append(current.rename(panel.index[stop]))
        rows.append(
            {
                "date": panel.index[stop],
                "gross": gross,
                "net": net,
                "turnover": turnover,
                "cost": cost,
                "train_end": panel.index[stop - 1],
            }
        )
    return pd.DataFrame(rows).set_index("date"), pd.DataFrame(weights)
