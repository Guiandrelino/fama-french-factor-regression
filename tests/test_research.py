import io
import json
import zipfile

import numpy as np
import pandas as pd
import pytest
import statsmodels.api as sm

from factorlab.data import demo_data, monthly_returns
from factorlab.provenance import cache_status, manifest, snapshot
from factorlab.report import export_bundle, html_report
from factorlab.research import compare, parse_weights, portfolio_returns, walk_forward


def panel_data():
    returns, factors = demo_data()
    return pd.DataFrame({"A": returns, "B": returns * 0.8}), factors


@pytest.mark.parametrize("policy", ["monthly", "buy_hold"])
def test_portfolio(policy):
    index = pd.date_range("2020-01-31", periods=3, freq="ME")
    r = pd.DataFrame({"A": [0.1, 0.2, -0.1], "B": [0, 0.05, 0.02]}, index=index)
    result, history = portfolio_returns(r, {"A": 0.5, "B": 0.5}, policy)
    assert result.iloc[0] == pytest.approx(0.05)
    if policy == "monthly":
        np.testing.assert_allclose(result, [0.05, 0.125, -0.04])
    else:
        terminal = 0.5 * (1 + r.A).prod() + 0.5 * (1 + r.B).prod()
        assert (1 + result).prod() == pytest.approx(terminal)
        assert history.iloc[1].A == pytest.approx(0.55 / 1.05)
    np.testing.assert_allclose(history.sum(axis=1), 1)


@pytest.mark.parametrize("weights", [{"A": 0.3}, {"A": -1, "B": 2}, {"C": 1}, {"A": np.nan}])
def test_invalid_weights(weights):
    with pytest.raises(ValueError):
        portfolio_returns(panel_data()[0], weights)


def test_parse_weights():
    assert parse_weights("A: 30%\nB: 0.7") == {"A": 0.3, "B": 0.7}
    with pytest.raises(ValueError):
        parse_weights("A: 30%\nA: 70%")


def test_same_sample_and_model_metrics():
    panel, factors = panel_data()
    study = compare(
        panel, {"CAPM": factors.iloc[10:], "FF3": factors, "FF5": factors.iloc[:-5]}, "B"
    )
    assert len(study.returns) == 165
    for result in study.results.values():
        assert result.data.index.equals(study.returns.index)
        x = sm.add_constant(result.data[[c for c in result.coefficients.index if c != "alpha"]])
        fitted = sm.OLS(result.data.excess_return, x).fit()
        assert result.metrics["aic"] == pytest.approx(fitted.aic)
        assert result.metrics["bic"] == pytest.approx(fitted.bic)
    assert study.summary.loc[("B", "CAPM"), "tracking_error_annual"] == 0


def test_walk_forward_no_lookahead():
    panel, factors = panel_data()
    result = walk_forward(panel.A, factors, "FF3", 60)
    assert len(result) == 120
    assert (result.train_end < result.index).all()
    changed = panel.A.copy()
    changed.iloc[60] += 0.1
    altered = walk_forward(changed, factors, "FF3", 60)
    assert altered.iloc[0].explained_excess == pytest.approx(result.iloc[0].explained_excess)
    assert altered.iloc[0].error - result.iloc[0].error == pytest.approx(0.1)
    with pytest.raises(ValueError):
        walk_forward(panel.A.iloc[:60], factors, "FF3", 60)


def test_report_bundle_and_hashes(tmp_path):
    panel, factors = panel_data()
    study = compare(panel, {"FF3": factors}, "B")
    metadata = manifest({"policy": "monthly"}, {"returns": panel}, tmp_path)
    html = html_report(study, metadata)
    assert "intervalo de confiança" in html
    assert "plotly" in html
    with zipfile.ZipFile(io.BytesIO(export_bundle(study, metadata))) as archive:
        assert {"summary.csv", "report.html", "manifest.json"}.issubset(archive.namelist())
        assert json.loads(archive.read("manifest.json"))["schema_version"] == 1
    first = snapshot(b"abc", "test", tmp_path)
    assert first["sha256"] == snapshot(b"abc", "test", tmp_path)["sha256"]
    assert first["sha256"] != snapshot(b"abd", "test", tmp_path)["sha256"]
    assert cache_status(tmp_path) == []


def test_nyse_good_friday_and_partial_month():
    # 29/03/2024 foi feriado (Good Friday), último pregão = dia 28.
    prices = pd.Series(
        [100, 110, 120], index=pd.to_datetime(["2024-02-29", "2024-03-28", "2024-04-15"])
    )
    result = monthly_returns(prices)
    assert len(result) == 1
    assert result.iloc[0] == pytest.approx(0.1)
