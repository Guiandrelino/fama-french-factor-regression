import numpy as np
import pandas as pd
import pytest

from factorlab.alerts import exposure_alerts
from factorlab.data import demo_data
from factorlab.evaluation import performance_metrics, rolling_allocation
from factorlab.quality import audit_panel
from factorlab.regression import fit_model
from factorlab.security import backup_database, password_hash, restore_database, verify_password
from factorlab.storage import AnalysisStore
from factorlab.uncertainty import bootstrap_risk, bootstrap_weights


def panel():
    r, f = demo_data()
    return pd.DataFrame(
        {"A": r, "B": r * 0.6 + np.random.default_rng(1).normal(0, 0.01, len(r))}
    ), f


def test_quality_no_mutation():
    p, f = panel()
    p.iloc[4, 0] = np.nan
    before = p.copy()
    quality, extremes, common = audit_panel(p, {"FF5": f}, "USD", "fixture")
    assert quality.iloc[0].status == "erro"
    assert "2010-05" in quality.iloc[0].missing_months
    assert len(common) == len(p) - 1
    pd.testing.assert_frame_equal(before, p)


def test_costs_groups_and_rolling_no_future():
    p, _ = panel()
    a, w = rolling_allocation(
        p,
        60,
        cost_bps=10,
        max_weight=0.7,
        groups={"A": "tech", "B": "other"},
        group_caps={"tech": 0.6},
    )
    assert (w.A <= 0.600001).all()
    assert (a.net <= a.gross + 1e-12).all()
    changed = p.copy()
    changed.iloc[60:] *= 2
    _, new_w = rolling_allocation(changed, 60, max_weight=0.7)
    _, old_w = rolling_allocation(p, 60, max_weight=0.7)
    np.testing.assert_allclose(new_w.iloc[0], old_w.iloc[0])
    assert np.isfinite(performance_metrics(a[["gross", "net"]]).to_numpy()).all()


def test_bootstrap_reproducible():
    p, f = panel()
    r = fit_model(p.A, f)
    draws, ci = bootstrap_risk(r, 20, 6)
    assert len(draws) == 20
    assert (ci.low_95 <= ci.high_95).all()
    weights, _ = bootstrap_weights(p.iloc[:60], 20, 6, max_weight=0.7)
    np.testing.assert_allclose(weights.sum(axis=1), 1)


def test_auth_backup_restore(tmp_path):
    encoded = password_hash("correct")
    assert verify_password("correct", encoded)
    assert not verify_password("wrong", encoded)
    assert not verify_password("wrong", "invalid")
    store = AnalysisStore(tmp_path / "test.sqlite")
    raw = backup_database(store.path)
    restore_database(store.path, raw)
    assert store.list().empty
    with pytest.raises(ValueError):
        restore_database(store.path, b"invalid")


def test_alerts():
    current = pd.DataFrame(
        {"beta_Mkt-RF": [1.5], "beta_HML": [-0.2], "residual_vol_annual": [0.2]}, index=["A"]
    )
    old = pd.DataFrame(
        {"beta_Mkt-RF": [1.0], "beta_HML": [0.2], "residual_vol_annual": [0.1]}, index=["A"]
    )
    assert len(exposure_alerts(current, old, stale=True)) == 4
