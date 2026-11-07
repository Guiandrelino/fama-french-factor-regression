"""Mínima variância regularizada, long-only, com limites de beta opcionais."""

import numpy as np
import pandas as pd
from scipy.optimize import minimize

from factorlab.research import validate_panel


def optimize_portfolio(
    returns,
    max_weight=0.5,
    ridge=0.1,
    exposures=None,
    beta_bounds=None,
    groups=None,
    group_caps=None,
):
    returns = validate_panel(returns)
    if len(returns) < 24 or not 0 < max_weight <= 1 or not 0 <= ridge <= 1:
        raise ValueError("Exige 24 meses, limite em (0,1] e regularização em [0,1].")
    n = returns.shape[1]
    if n * max_weight < 1 - 1e-9:
        raise ValueError("Limite por ativo inviável para somar 100%.")
    covariance = returns.cov().to_numpy() * 12
    covariance = (1 - ridge) * covariance + ridge * np.diag(np.diag(covariance))
    covariance += np.eye(n) * 1e-10
    constraints = [{"type": "eq", "fun": lambda w: w.sum() - 1}]
    for group, cap in (group_caps or {}).items():
        if groups is None or set(returns.columns) - set(groups) or not 0 <= cap <= 1:
            raise ValueError("Grupos incompletos ou limite inválido.")
        mask = np.array([groups[a] == group for a in returns.columns], dtype=float)
        constraints.append({"type": "ineq", "fun": lambda w, m=mask, c=cap: c - w @ m})
    for factor, (low, high) in (beta_bounds or {}).items():
        if exposures is None or factor not in exposures or low > high:
            raise ValueError("Limites de beta ou exposições inválidos.")
        beta = exposures.loc[returns.columns, factor].to_numpy(dtype=float)
        if not np.isfinite(beta).all():
            raise ValueError("Exposições não finitas.")
        constraints.extend(
            [
                {"type": "ineq", "fun": lambda w, b=beta, lower=low: w @ b - lower},
                {"type": "ineq", "fun": lambda w, b=beta, h=high: h - w @ b},
            ]
        )
    fit = minimize(
        lambda w: w @ covariance @ w,
        np.repeat(1 / n, n),
        jac=lambda w: 2 * covariance @ w,
        method="SLSQP",
        bounds=[(0, max_weight)] * n,
        constraints=constraints,
        options={"ftol": 1e-12, "maxiter": 1000},
    )
    if not fit.success or any(
        np.min(c["fun"](fit.x)) < -1e-6 for c in constraints if c["type"] == "ineq"
    ):
        raise ValueError(f"Otimização inviável ou sem convergência: {fit.message}")
    weights = pd.Series(fit.x, index=returns.columns, name="weight")
    return weights, float(np.sqrt(weights @ covariance @ weights))


def holdout_optimization(
    returns, train_months, max_weight=0.5, ridge=0.1, exposures=None, beta_bounds=None
):
    returns = validate_panel(returns)
    if train_months < 24 or len(returns) - train_months < 12:
        raise ValueError("Use pelo menos 24 meses de treino e 12 de avaliação.")
    train, test = returns.iloc[:train_months], returns.iloc[train_months:]
    weights, estimated_vol = optimize_portfolio(train, max_weight, ridge, exposures, beta_bounds)
    # Pesos fixos representam rebalanceamento mensal, não buy-and-hold.
    performance = pd.DataFrame({"optimized": test @ weights, "equal_weight": test.mean(axis=1)})
    return weights, estimated_vol, performance
