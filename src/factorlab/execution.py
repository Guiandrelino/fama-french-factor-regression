"""Avaliação comparável com custos e RF para estratégia e referências."""

import numpy as np
import pandas as pd

from factorlab.evaluation import performance_metrics, rolling_allocation


def fixed_allocation_net(panel, cost_bps):
    target = pd.Series(1 / panel.shape[1], index=panel.columns)
    previous = None
    values = []
    for _, row in panel.iterrows():
        turnover = 1.0 if previous is None else float((target - previous).abs().sum() / 2)
        gross = float(row @ target)
        if gross <= -1:
            raise ValueError("Referência perdeu todo o patrimônio.")
        values.append((1 - turnover * cost_bps / 10000) * (1 + gross) - 1)
        previous = target * (1 + row) / (1 + gross)
    return pd.Series(values, index=panel.index)


def evaluate_execution(panel, benchmark, rf, parameters):
    result, weights = rolling_allocation(panel, **parameters)
    test = panel.loc[result.index]
    comparison = result[["gross", "net"]].rename(
        columns={"gross": "strategy_gross", "net": "strategy_net"}
    )
    comparison["equal_weight_net"] = fixed_allocation_net(test, parameters["cost_bps"])
    comparison["benchmark_net"] = fixed_allocation_net(
        benchmark.loc[result.index].to_frame(), parameters["cost_bps"]
    )
    metrics = performance_metrics(comparison, rf)
    if not np.isfinite(comparison.to_numpy()).all():
        raise ValueError("Avaliação contém valores inválidos.")
    return {
        "execution_returns": comparison,
        "execution_cost_turnover": result[["cost", "turnover"]],
        "execution_metrics": metrics,
        "execution_weights": weights,
        "execution_parameters": pd.DataFrame(
            [
                {
                    "parameters": str(parameters),
                    "reference_policy": "monthly; same cost bps; initial entry charged",
                }
            ]
        ),
    }
