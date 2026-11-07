"""Brasil: fatores NEFIN mensais value-weighted, retornos em BRL."""

import io

import numpy as np
import pandas as pd

from factorlab.data import cached_download

NEFIN_URL = "https://nefin.com.br/nefindata/risk-factors/nefin_factors_monthly.csv"
BR_MODELS = ["CAPM", "FF3", "CARHART4"]


def load_nefin(cache_dir=".cache", refresh=False):
    raw, metadata = cached_download(NEFIN_URL, "nefin_monthly.csv", cache_dir, refresh)
    frame = pd.read_csv(io.BytesIO(raw))
    frame.index = pd.to_datetime(dict(year=frame.year, month=frame.month, day=1))
    frame.index = frame.index.to_period("M").to_timestamp("M")
    frame = frame.rename(columns={"Rm_minus_Rf": "Mkt-RF", "WML": "Mom", "Risk_Free": "RF"})
    frame = frame[["Mkt-RF", "SMB", "HML", "Mom", "RF"]].astype(float).sort_index()
    if frame.index.has_duplicates or not np.isfinite(frame).all().all():
        raise ValueError("NEFIN contém meses duplicados ou valores inválidos.")
    frame.attrs["provenance"] = {"NEFIN": metadata}
    return frame
