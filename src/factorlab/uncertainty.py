"""Moving-block bootstrap: preserva dependência local, não regimes completos."""

import numpy as np
import pandas as pd
import statsmodels.api as sm

from factorlab.optimization import optimize_portfolio


def block_indices(n, block, rng):
    if not 1 <= block <= n:
        raise ValueError("Bloco fora da amostra.")
    starts = rng.integers(0, n - block + 1, size=int(np.ceil(n / block)))
    return np.concatenate([np.arange(s, s + block) for s in starts])[:n]


def bootstrap_risk(result, repetitions=100, block=6, seed=42):
    if not 20 <= repetitions <= 500:
        raise ValueError("Use de 20 a 500 réplicas.")
    rng = np.random.default_rng(seed)
    names = result.coefficients.index.drop("alpha")
    rows = []
    for _ in range(repetitions):
        data = result.data.iloc[block_indices(len(result.data), block, rng)]
        x = sm.add_constant(data[names], has_constant="add")
        if np.linalg.matrix_rank(x) < x.shape[1]:
            raise ValueError("Réplica bootstrap singular.")
        fit = sm.OLS(data.excess_return, x).fit()
        beta = fit.params[names]
        contribution = beta * (data[names].cov() @ beta) * 12
        rows.append(
            {
                **{f"beta_{n}": beta[n] for n in names},
                **{f"risk_{n}": contribution[n] for n in names},
            }
        )
    draws = pd.DataFrame(rows)
    return draws, draws.quantile([0.025, 0.5, 0.975]).T.rename(
        columns={0.025: "low_95", 0.5: "median", 0.975: "high_95"}
    )


def bootstrap_weights(panel, repetitions=100, block=6, max_weight=0.6, ridge=0.1, seed=42):
    if not 20 <= repetitions <= 500:
        raise ValueError("Use de 20 a 500 réplicas.")
    rng = np.random.default_rng(seed)
    draws = []
    for _ in range(repetitions):
        sample = panel.iloc[block_indices(len(panel), block, rng)].copy()
        sample.index = pd.date_range("2000-01-31", periods=len(sample), freq="ME")
        weights, _ = optimize_portfolio(sample, max_weight, ridge)
        draws.append(weights)
    frame = pd.DataFrame(draws)
    return frame, frame.quantile([0.025, 0.5, 0.975]).T


def allocation_sensitivity(panel, windows=(36, 60, 84), ridges=(0.0, 0.1, 0.5), max_weight=0.6):
    rows = []
    for window in windows:
        if window <= len(panel):
            for ridge in ridges:
                weights, _ = optimize_portfolio(panel.iloc[-window:], max_weight, ridge)
                rows.append({"window": window, "ridge": ridge, **weights.to_dict()})
    return pd.DataFrame(rows)
