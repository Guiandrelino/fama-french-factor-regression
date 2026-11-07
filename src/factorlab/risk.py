"""Risco de fatores com covariâncias e cenários condicionais mensais."""

import numpy as np
import pandas as pd


def risk_decomposition(result):
    names = result.coefficients.index.drop("alpha")
    beta = result.coefficients.loc[names, "coefficient"]
    covariance = result.data[names].cov(ddof=1)
    contributions = beta * (covariance @ beta) * 12
    residual = result.residuals.var(ddof=1) * 12
    total = float(contributions.sum() + residual)
    table = contributions.rename("variance_annual").to_frame()
    table.loc["Residual", "variance_annual"] = residual
    table["share"] = table.variance_annual / total if total > 0 else np.nan
    return table, {
        "systematic_vol_annual": float(np.sqrt(max(contributions.sum(), 0))),
        "residual_vol_annual": float(np.sqrt(residual)),
        "total_vol_annual": float(np.sqrt(total)),
    }


def stress_scenario(result, shocks, include_alpha=False):
    """Choques são retornos dos fatores, não variações de preços ou betas."""
    names = result.coefficients.index.drop("alpha")
    if set(shocks) != set(names):
        raise ValueError("Informe exatamente os fatores do modelo; use zero nos demais.")
    shock = pd.Series(shocks, dtype=float).reindex(names)
    if not np.isfinite(shock).all():
        raise ValueError("Choques devem ser finitos.")
    table = pd.DataFrame(
        {"factor_return": shock, "beta": result.coefficients.loc[names, "coefficient"]}
    )
    table["impact"] = table.factor_return * table.beta
    impact = table.impact.sum()
    if include_alpha:
        impact += result.coefficients.loc["alpha", "coefficient"]
    return table, float(impact)


def historical_stress(result, start, end):
    """Reaplica fatores observados aos betas atuais; não reproduz carteira histórica."""
    names = result.coefficients.index.drop("alpha")
    frame = result.data.loc[start:end, names]
    if frame.empty:
        raise ValueError("Cenário fora da amostra de fatores desta análise.")
    impacts = frame @ result.coefficients.loc[names, "coefficient"]
    return impacts.rename("systematic_monthly_impact")
