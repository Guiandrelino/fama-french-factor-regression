"""Comparações em amostra comum, carteira long-only e avaliação retrospectiva."""

from dataclasses import dataclass

import numpy as np
import pandas as pd
import statsmodels.api as sm

from factorlab.regression import MODELS, RegressionResult, fit_model


def validate_panel(returns: pd.DataFrame) -> pd.DataFrame:
    if returns.empty or returns.columns.has_duplicates or returns.index.has_duplicates:
        raise ValueError("Painel vazio ou com ativos/datas duplicados.")
    if not isinstance(returns.index, pd.DatetimeIndex) or returns.index.hasnans:
        raise ValueError("Painel deve conter datas válidas.")
    if not returns.index.equals(returns.index.to_period("M").to_timestamp("M")):
        raise ValueError("Use datas no fim do mês.")
    returns = returns.sort_index().astype(float)
    if not np.isfinite(returns.to_numpy()).all() or (returns < -1).any().any():
        raise ValueError("Painel contém retornos ausentes, não finitos ou inferiores a -100%.")
    if len(pd.period_range(returns.index.min(), returns.index.max(), freq="M")) != len(returns):
        raise ValueError("Painel contém meses ausentes.")
    return returns


def parse_weights(text: str) -> dict[str, float]:
    weights = {}
    for line in text.strip().splitlines():
        ticker, value = line.split(":", 1)
        ticker, value = ticker.strip().upper(), value.strip()
        if not ticker or ticker in weights:
            raise ValueError("Ativo vazio ou repetido nos pesos.")
        weights[ticker] = float(value.rstrip("%")) / (100 if value.endswith("%") else 1)
    return weights


def portfolio_returns(
    returns: pd.DataFrame, weights: dict[str, float], policy: str = "monthly"
) -> tuple[pd.Series, pd.DataFrame]:
    returns = validate_panel(returns)
    if not weights or set(weights) - set(returns.columns):
        raise ValueError("Pesos devem referenciar ativos disponíveis.")
    w = pd.Series(weights, dtype=float)
    if not np.isfinite(w).all() or (w < 0).any() or not np.isclose(w.sum(), 1, atol=1e-8):
        raise ValueError("Pesos long-only devem ser finitos, não negativos e somar 100%.")
    r = returns[w.index]
    if policy == "monthly":
        history = pd.DataFrame(np.tile(w.to_numpy(), (len(r), 1)), index=r.index, columns=w.index)
    elif policy == "buy_hold":
        wealth_before = (1 + r).cumprod().shift(1, fill_value=1).mul(w)
        total = wealth_before.sum(axis=1)
        if (total <= 0).any():
            raise ValueError("Carteira sem patrimônio após perda total; pesos indefinidos.")
        history = wealth_before.div(total, axis=0)
    else:
        raise ValueError("Política deve ser monthly ou buy_hold.")
    return (r * history).sum(axis=1).rename("Carteira"), history


@dataclass
class Study:
    results: dict[tuple[str, str], RegressionResult]
    summary: pd.DataFrame
    returns: pd.DataFrame
    benchmark: str


def compare(
    returns: pd.DataFrame,
    factor_sets: dict[str, pd.DataFrame],
    benchmark: str,
    hac_lags: int = 3,
    rolling_window: int = 36,
) -> Study:
    if benchmark not in returns:
        raise ValueError("Benchmark ausente do painel.")
    if not factor_sets:
        raise ValueError("Selecione pelo menos um modelo.")
    returns = validate_panel(returns)
    index = returns.index
    for model, factors in factor_sets.items():
        if model not in MODELS:
            raise ValueError("Modelo inválido.")
        if factors.index.has_duplicates:
            raise ValueError("Fatores com datas duplicadas.")
        needed = [*MODELS[model], "RF"]
        if set(needed) - set(factors):
            raise ValueError(f"Fatores ausentes para {model}.")
        index = index.intersection(factors[needed].dropna().index)
    returns = returns.loc[index].sort_index()
    returns = validate_panel(returns)
    results, rows = {}, []
    for asset in returns:
        active = returns[asset] - returns[benchmark]
        tracking_error = active.std(ddof=1) * np.sqrt(12)
        for model, factors in factor_sets.items():
            result = fit_model(
                returns[asset], factors.loc[returns.index], model, hac_lags, rolling_window
            )
            results[asset, model] = result
            row = {
                "asset": asset,
                "model": model,
                **result.metrics,
                "alpha_ci_low": result.coefficients.loc["alpha", "ci_95_low"],
                "alpha_ci_high": result.coefficients.loc["alpha", "ci_95_high"],
                "tracking_error_annual": tracking_error,
                "active_return_annual_arithmetic": 12 * active.mean(),
                "cumulative_return": (1 + returns[asset]).prod() - 1,
            }
            for factor, value in result.coefficients.coefficient.items():
                row[f"beta_{factor}" if factor != "alpha" else "alpha"] = value
            for factor, value in result.rolling.std(ddof=1).items():
                row[f"rolling_std_{factor}"] = value
            rows.append(row)
    return Study(results, pd.DataFrame(rows).set_index(["asset", "model"]), returns, benchmark)


def walk_forward(
    returns: pd.Series, factors: pd.DataFrame, model: str, train_window: int = 60
) -> pd.DataFrame:
    """Usa betas anteriores com fatores REALIZADOS no mês de teste (não previsão)."""
    if model not in MODELS or train_window < 24:
        raise ValueError("Modelo inválido ou treino menor que 24 meses.")
    baseline = fit_model(returns, factors, model, rolling_window=train_window)
    data = baseline.data
    if len(data) <= train_window:
        raise ValueError("Amostra deve ser maior que a janela de treino.")
    columns = MODELS[model]
    rows = []
    for stop in range(train_window, len(data)):
        train = data.iloc[stop - train_window : stop]
        x = sm.add_constant(train[columns], has_constant="add")
        if np.linalg.matrix_rank(x) < x.shape[1]:
            raise ValueError("Janela de treino singular.")
        params = sm.OLS(train.excess_return, x).fit().params
        row = data.iloc[stop]
        fitted = params["const"] + row[columns] @ params[columns]
        rows.append(
            {
                "date": data.index[stop],
                "train_end": train.index[-1],
                "actual_excess": row.excess_return,
                "explained_excess": fitted,
                "error": row.excess_return - fitted,
                **{f"beta_{k}": v for k, v in params.items()},
            }
        )
    return pd.DataFrame(rows).set_index("date")
