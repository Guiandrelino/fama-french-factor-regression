import numpy as np
import pandas as pd
import pytest

from factorlab.data import demo_data
from factorlab.diagnostics import advanced_diagnostics, hac_sensitivity
from factorlab.optimization import holdout_optimization, optimize_portfolio
from factorlab.regression import fit_model
from factorlab.research import compare
from factorlab.risk import historical_stress, risk_decomposition, stress_scenario
from factorlab.storage import AnalysisStore, compare_saved


def result():
    return fit_model(*demo_data(), "FF5")


def test_risk_covariance_reconciles():
    fit = result()
    table, metrics = risk_decomposition(fit)
    assert table.variance_annual.sum() == pytest.approx(fit.data.excess_return.var() * 12)
    assert table.share.sum() == pytest.approx(1)
    assert metrics["total_vol_annual"] ** 2 == pytest.approx(table.variance_annual.sum())


def test_stress():
    fit = result()
    shocks = dict.fromkeys(fit.coefficients.index.drop("alpha"), 0.0)
    shocks["Mkt-RF"] = -0.1
    _, impact = stress_scenario(fit, shocks)
    assert impact == pytest.approx(-0.1 * fit.coefficients.loc["Mkt-RF", "coefficient"])
    assert len(historical_stress(fit, "2020-03", "2020-03")) == 1
    with pytest.raises(ValueError):
        stress_scenario(fit, {"Mkt-RF": -0.1})
    with pytest.raises(ValueError):
        historical_stress(fit, "1900", "1901")


def test_sqlite_roundtrip_delete_and_compare(tmp_path):
    returns, factors = demo_data()
    study = compare(returns.to_frame("SPY"), {"FF3": factors}, "SPY")
    store = AnalysisStore(tmp_path / "test.sqlite")
    identifier = store.save("Example", study, {"parameters": {"source": "demo"}})
    loaded = store.load(identifier)
    assert loaded["name"] == "Example"
    np.testing.assert_allclose(loaded["summary"], study.summary, atol=1e-9)
    assert compare_saved(loaded, loaded).abs().max().max() == 0
    assert len(store.list()) == 1
    store.delete(identifier)
    assert store.list().empty
    with pytest.raises(ValueError):
        store.load(identifier)


def test_advanced_diagnostics():
    fit = result()
    corr, vif, influence = advanced_diagnostics(fit)
    assert corr.shape == (5, 5)
    assert (vif >= 1).all()
    assert len(influence) == len(fit.data)
    sensitivity = hac_sensitivity(fit)
    np.testing.assert_allclose(
        sensitivity.coefficient, fit.coefficients.loc["alpha", "coefficient"]
    )


def test_optimization_constraints_and_holdout_no_leakage():
    rng = np.random.default_rng(123)
    panel = pd.DataFrame(
        rng.normal(0, [0.01, 0.03, 0.05], (120, 3)),
        columns=["A", "B", "C"],
        index=pd.date_range("2010-01-31", periods=120, freq="ME"),
    )
    beta = pd.DataFrame({"Mkt-RF": [0.5, 1.0, 1.5]}, index=panel.columns)
    weights, _ = optimize_portfolio(panel, 0.6, 0.1, beta, {"Mkt-RF": (0.8, 1.1)})
    assert weights.sum() == pytest.approx(1)
    assert weights.max() <= 0.6 + 1e-7
    assert 0.8 - 1e-6 <= weights @ beta["Mkt-RF"] <= 1.1 + 1e-6
    first, _, performance = holdout_optimization(panel, 84, 0.6)
    changed = panel.copy()
    changed.iloc[84:] *= 5
    second, _, _ = holdout_optimization(changed, 84, 0.6)
    np.testing.assert_allclose(first, second)
    assert len(performance) == 36
    with pytest.raises(ValueError):
        optimize_portfolio(panel, 0.2)
    with pytest.raises(ValueError):
        optimize_portfolio(panel, 0.6, 0.1, beta, {"Mkt-RF": (3, 4)})
