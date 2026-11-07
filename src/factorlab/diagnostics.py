"""Multicolinearidade, influência e sensibilidade da inferência HAC."""

import pandas as pd
import statsmodels.api as sm
from statsmodels.stats.outliers_influence import variance_inflation_factor

from factorlab.regression import fit_model


def advanced_diagnostics(result):
    names = result.coefficients.index.drop("alpha")
    x = sm.add_constant(result.data[names], has_constant="add")
    fit = sm.OLS(result.data.excess_return, x).fit()
    influence = fit.get_influence()
    observations = pd.DataFrame(
        {
            "cooks_distance": influence.cooks_distance[0],
            "leverage": influence.hat_matrix_diag,
            "studentized_residual": influence.resid_studentized_internal,
        },
        index=result.data.index,
    )
    observations["cook_flag_4_over_n"] = observations.cooks_distance > 4 / len(x)
    vif = pd.Series(
        {
            name: variance_inflation_factor(x.to_numpy(), i)
            for i, name in enumerate(x.columns)
            if name != "const"
        },
        name="VIF",
    )
    return result.data[names].corr(), vif, observations


def hac_sensitivity(result, lags=(0, 3, 6, 12)):
    rows = []
    for lag in lags:
        if lag < len(result.data):
            fitted = fit_model(
                result.data.asset_return,
                result.data,
                result.model,
                hac_lags=lag,
                rolling_window=len(result.data) + 1,
            )
            alpha = fitted.coefficients.loc["alpha"]
            rows.append({"hac_lags": lag, **alpha.to_dict()})
    return pd.DataFrame(rows).set_index("hac_lags")
