import numpy as np
import pandas as pd
import pytest

from factorlab.data import demo_data, download_prices_with_retry
from factorlab.forecast import forecast_walk_forward
from factorlab.report import pdf_report
from factorlab.research import compare


def test_forecast_no_contemporaneous_target_or_factor_leakage():
    returns, factors = demo_data()
    original = forecast_walk_forward(returns, factors, "FF3", 60, 2)
    date = original.index[0]
    altered_returns = returns.copy()
    altered_returns.loc[date:] += 0.1
    altered_factors = factors.copy()
    altered_factors.loc[date:, "Mkt-RF"] += 0.1
    changed = forecast_walk_forward(altered_returns, altered_factors, "FF3", 60, 2)
    assert changed.iloc[0].predicted_return == pytest.approx(original.iloc[0].predicted_return)
    assert (original.train_end < original.index).all()
    assert (original.latest_factor_month < original.index).all()
    assert np.isfinite(original.predicted_return).all()


def test_pdf_native():
    returns, factors = demo_data()
    study = compare(returns.to_frame("SPY"), {"FF3": factors}, "SPY")
    result = pdf_report(study, {"source": "synthetic"})
    assert result.startswith(b"%PDF-")
    assert result.rstrip().endswith(b"%%EOF")
    assert len(result) > 3000


def test_retry_transient_failure(monkeypatch):
    frames = iter([TimeoutError("DNS"), pd.DataFrame(), pd.DataFrame({"Close": [100]})])

    def download(*args, **kwargs):
        value = next(frames)
        if isinstance(value, Exception):
            raise value
        return value

    monkeypatch.setattr("factorlab.data.yf.download", download)
    result = download_prices_with_retry("SPY", "2020-01-01", None, delay=0)
    assert result.Close.iloc[0] == 100


def test_retry_exhaustion(monkeypatch):
    def fail(*args, **kwargs):
        raise TimeoutError("DNS")

    monkeypatch.setattr("factorlab.data.yf.download", fail)
    with pytest.raises(ConnectionError, match="3 tentativas"):
        download_prices_with_retry("SPY", "2020-01-01", None, delay=0)
