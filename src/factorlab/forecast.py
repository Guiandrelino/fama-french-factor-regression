"""Previsão mensal ex ante: somente fatores conhecidos antes do mês-alvo."""

import numpy as np
import pandas as pd
import statsmodels.api as sm

from factorlab.regression import MODELS, fit_model


def forecast_walk_forward(returns, factors, model="FF3", train_window=60, publication_lag=2):
    """OLS de R_t sobre fatores t-lag. Lag é conservador, não calendário point-in-time.

    Publicações/revisões históricas não são versionadas por data de disponibilidade:
    esta avaliação não certifica um backtest investível point-in-time.
    """
    if model not in MODELS or train_window < 24 or publication_lag < 1:
        raise ValueError("Modelo, janela ou defasagem de publicação inválidos.")
    baseline = fit_model(returns, factors, model)
    data = baseline.data
    columns = MODELS[model]
    x = data[columns].shift(publication_lag)
    aligned = pd.concat([data.asset_return.rename("target"), x], axis=1).dropna()
    if len(aligned) <= train_window:
        raise ValueError("Amostra insuficiente para previsão com a janela e defasagem escolhidas.")
    rows = []
    for stop in range(train_window, len(aligned)):
        train = aligned.iloc[stop - train_window : stop]
        design = sm.add_constant(train[columns], has_constant="add")
        if np.linalg.matrix_rank(design) < design.shape[1]:
            raise ValueError("Janela de previsão singular.")
        fit = sm.OLS(train.target, design).fit()
        row = aligned.iloc[stop]
        predicted = float(fit.params["const"] + row[columns] @ fit.params[columns])
        naive = float(train.target.mean())
        rows.append(
            {
                "date": aligned.index[stop],
                "train_end": train.index[-1],
                "latest_factor_month": data.index[
                    data.index.get_loc(aligned.index[stop]) - publication_lag
                ],
                "predicted_return": predicted,
                "historical_mean_forecast": naive,
                "actual_return": row.target,
                "error": row.target - predicted,
                "baseline_error": row.target - naive,
            }
        )
    return pd.DataFrame(rows).set_index("date")
