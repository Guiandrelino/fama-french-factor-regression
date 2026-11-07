"""Alertas descritivos, nunca ordens automáticas."""

import pandas as pd


def exposure_alerts(
    current,
    reference,
    beta_limit=1.2,
    residual_increase=0.25,
    current_weights=None,
    target_weights=None,
    weight_tolerance=0.05,
    stale=False,
):
    rows = []
    for index, row in current.iterrows():
        if row.get("beta_Mkt-RF", 0) > beta_limit:
            rows.append({"analysis": str(index), "alert": "Beta de mercado acima do limite"})
        if index in reference.index:
            old = reference.loc[index]
            if row.get("beta_HML", 0) * old.get("beta_HML", 0) < 0:
                rows.append({"analysis": str(index), "alert": "Exposição a valor mudou de sinal"})
            if row.residual_vol_annual > old.residual_vol_annual * (1 + residual_increase):
                rows.append({"analysis": str(index), "alert": "Volatilidade residual aumentou"})
    if stale:
        rows.append({"analysis": "fontes", "alert": "Dados desatualizados"})
    if current_weights is not None and target_weights is not None:
        actual, target = pd.Series(current_weights).align(pd.Series(target_weights), fill_value=0)
        for asset in actual.index[(actual - target).abs() > weight_tolerance]:
            rows.append({"analysis": asset, "alert": "Peso afastado da alocação-alvo"})
    return pd.DataFrame(rows, columns=["analysis", "alert"])
