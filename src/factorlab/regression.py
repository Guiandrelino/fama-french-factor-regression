"""OLS de retornos excedentes com erros-padrão Newey–West (HAC)."""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd
import statsmodels.api as sm
from statsmodels.stats.diagnostic import acorr_ljungbox, het_breuschpagan
from statsmodels.stats.stattools import durbin_watson, jarque_bera

MODELS = {
    "CAPM": ["Mkt-RF"],
    "FF3": ["Mkt-RF", "SMB", "HML"],
    "FF5": ["Mkt-RF", "SMB", "HML", "RMW", "CMA"],
    "CARHART4": ["Mkt-RF", "SMB", "HML", "Mom"],
    "FF6": ["Mkt-RF", "SMB", "HML", "RMW", "CMA", "Mom"],
}


@dataclass
class RegressionResult:
    model: str
    data: pd.DataFrame
    coefficients: pd.DataFrame
    metrics: dict
    diagnostics: dict
    fitted: pd.Series
    residuals: pd.Series
    rolling: pd.DataFrame


def fit_model(
    returns: pd.Series,
    factors: pd.DataFrame,
    model: str = "FF5",
    hac_lags: int = 3,
    rolling_window: int = 36,
) -> RegressionResult:
    if model not in MODELS:
        raise ValueError(f"Escolha um dos modelos: {', '.join(MODELS)}.")
    columns = MODELS[model]
    missing = {*columns, "RF"} - set(factors.columns)
    if missing:
        raise ValueError(f"Fatores ausentes: {', '.join(sorted(missing))}")
    if returns.index.has_duplicates or factors.index.has_duplicates:
        raise ValueError("Índices não podem conter meses duplicados.")
    for index in (returns.index, factors.index):
        if not isinstance(index, pd.DatetimeIndex):
            raise TypeError("Use DatetimeIndex com datas no fim do mês.")
        if index.hasnans:
            raise ValueError("Datas ausentes não são permitidas.")
        if not index.equals(index.to_period("M").to_timestamp("M")):
            raise ValueError("Datas devem estar normalizadas para o fim do mês.")
    data = (
        pd.concat([returns.rename("asset_return"), factors[[*columns, "RF"]]], axis=1, join="inner")
        .sort_index()
        .dropna()
    )
    if len(data) < max(24, len(columns) + 3):
        raise ValueError("São necessários pelo menos 24 meses completos em comum.")
    if not np.isfinite(data.to_numpy()).all():
        raise ValueError("Dados contêm valores não finitos.")
    if (data["asset_return"] < -1).any():
        raise ValueError("Retorno simples não pode ser inferior a -100%.")
    # HAC/rolling pressupõem observações mensais consecutivas.
    if len(pd.period_range(data.index.min(), data.index.max(), freq="M")) != len(data):
        raise ValueError("Há meses ausentes na amostra alinhada. Use um intervalo contínuo.")
    if not 0 <= hac_lags < len(data):
        raise ValueError("Defasagens HAC devem estar entre zero e n-1.")
    if rolling_window < len(columns) + 3:
        raise ValueError("Janela móvel pequena demais para o modelo.")
    y = data["asset_return"] - data["RF"]
    x = sm.add_constant(data[columns], has_constant="add")
    if np.linalg.matrix_rank(x.to_numpy()) < x.shape[1]:
        raise ValueError("Matriz de fatores singular: fatores constantes ou colineares.")
    fit = sm.OLS(y, x).fit(cov_type="HAC", cov_kwds={"maxlags": hac_lags}, use_t=True)
    ci = fit.conf_int()
    table = pd.DataFrame(
        {
            "coefficient": fit.params,
            "std_error_HAC": fit.bse,
            "t_stat": fit.tvalues,
            "p_value": fit.pvalues,
            "ci_95_low": ci[0],
            "ci_95_high": ci[1],
        }
    )
    table.index.name = "factor"
    table = table.rename(index={"const": "alpha"})
    residuals = fit.resid.rename("residual")
    jb = jarque_bera(residuals)
    bp = het_breuschpagan(residuals, x)
    lb = acorr_ljungbox(residuals, lags=[min(12, len(data) // 5)], return_df=True)
    metrics = {
        "observations": int(fit.nobs),
        "r_squared": float(fit.rsquared),
        "adjusted_r_squared": float(fit.rsquared_adj),
        "alpha_monthly": float(fit.params["const"]),
        "alpha_annual_arithmetic": float(12 * fit.params["const"]),
        "residual_vol_annual": float(residuals.std(ddof=x.shape[1]) * np.sqrt(12)),
        "aic": float(fit.aic),
        "bic": float(fit.bic),
        "residual_rmse": float(np.sqrt(np.mean(residuals**2))),
        "condition_number": float(fit.condition_number),
        "hac_lags": hac_lags,
    }
    diagnostics = {
        "durbin_watson": float(durbin_watson(residuals)),
        "jarque_bera_p": float(jb[1]),
        "breusch_pagan_p": float(bp[1]),
        "ljung_box_p": float(lb["lb_pvalue"].iloc[0]),
    }
    rolling_rows = []
    for stop in range(rolling_window, len(data) + 1):
        window_x = x.iloc[stop - rolling_window : stop]
        if np.linalg.matrix_rank(window_x.to_numpy()) < window_x.shape[1]:
            continue
        params = sm.OLS(y.iloc[stop - rolling_window : stop], window_x).fit().params
        params.name = data.index[stop - 1]
        rolling_rows.append(params)
    rolling = pd.DataFrame(rolling_rows).rename(columns={"const": "alpha"})
    rolling.index.name = "date"
    data = data.assign(excess_return=y)
    return RegressionResult(
        model,
        data,
        table,
        metrics,
        diagnostics,
        fit.fittedvalues.rename("fitted_excess"),
        residuals,
        rolling,
    )
