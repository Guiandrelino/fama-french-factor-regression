import threading

import numpy as np
import pandas as pd
import pytest

from factorlab.data import demo_data, load_prices
from factorlab.evaluation import performance_metrics
from factorlab.execution import fixed_allocation_net
from factorlab.operations import BoundedExecutor
from factorlab.research import compare
from factorlab.runtime import enforce_quota
from factorlab.storage import AnalysisStore


def test_price_cache_expiry_isolation_and_network_failure(tmp_path, monkeypatch):
    monkeypatch.setattr("factorlab.security.workspace_root", lambda: tmp_path / "alice")
    (tmp_path / "alice").mkdir()
    calls = []

    def download(*a, **kw):
        calls.append(1)
        return pd.DataFrame(
            {"Close": [100.0, 101.0]}, index=pd.to_datetime(["2020-01-30", "2020-01-31"])
        )

    monkeypatch.setattr("factorlab.data.download_prices_with_retry", download)
    first = load_prices("SPY", "2020-01-01", "2020-02-01")
    second = load_prices("SPY", "2020-01-01", "2020-02-01")
    assert len(calls) == 1 and second.attrs["provenance"]["cache_used"]
    np.testing.assert_allclose(first, second)
    monkeypatch.setattr("factorlab.security.workspace_root", lambda: tmp_path / "bob")
    (tmp_path / "bob").mkdir()
    load_prices("SPY", "2020-01-01", "2020-02-01")
    assert len(calls) == 2

    def fail(*a, **kw):
        raise ConnectionError("DNS")

    monkeypatch.setattr("factorlab.data.download_prices_with_retry", fail)
    with pytest.raises(ConnectionError):
        load_prices("SPY", "2020-01-01", "2020-02-01", cache_ttl=-1)


def test_cost_identity_and_rf():
    index = pd.date_range("2020-01-31", periods=3, freq="ME")
    panel = pd.DataFrame({"A": [0.1, 0.0, 0.05]}, index=index)
    net = fixed_allocation_net(panel, 10)
    assert net.iloc[0] == pytest.approx(0.999 * 1.1 - 1)
    assert net.iloc[1] == 0
    result = performance_metrics(panel, pd.Series(0.001, index=index))
    assert "sharpe_excess" in result


def test_saved_artifacts_and_quota(tmp_path, monkeypatch):
    r, f = demo_data()
    study = compare(r.to_frame("SPY"), {"FF3": f}, "SPY")
    store = AnalysisStore(tmp_path / "a.sqlite")
    identifier = store.save(
        "complete", study, {}, {"weights": pd.DataFrame({"weight": [1.0]}, index=["SPY"])}
    )
    assert store.load(identifier)["extras"]["weights"].iloc[0, 0] == 1
    monkeypatch.setenv("FACTORLAB_QUOTA_MB", "0")
    with pytest.raises(ValueError):
        enforce_quota(tmp_path, 1)


def test_global_queue_is_bounded():
    executor = BoundedExecutor(workers=1, capacity=1)
    event = threading.Event()
    future = executor.submit(event.wait, 5)
    try:
        with pytest.raises(ValueError, match="Fila global"):
            executor.submit(lambda: None)
    finally:
        event.set()
        future.result(timeout=10)
        executor.pool.shutdown()
