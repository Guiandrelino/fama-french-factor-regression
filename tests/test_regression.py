import numpy as np
import pandas as pd
import pytest
import statsmodels.api as sm

from factorlab.data import demo_data
from factorlab.regression import MODELS, fit_model


@pytest.mark.parametrize("model", MODELS)
def test_coefficients_hac_and_rolling_against_statsmodels(model):
    returns, factors = demo_data()
    result = fit_model(returns, factors, model)
    x = sm.add_constant(factors[MODELS[model]])
    expected = sm.OLS(returns - factors.RF, x).fit(
        cov_type="HAC", cov_kwds={"maxlags": 3}, use_t=True
    )
    np.testing.assert_allclose(result.coefficients.coefficient, expected.params)
    np.testing.assert_allclose(result.coefficients.std_error_HAC, expected.bse)
    np.testing.assert_allclose(result.coefficients.p_value, expected.pvalues)
    np.testing.assert_allclose(
        result.coefficients[["ci_95_low", "ci_95_high"]], expected.conf_int()
    )
    assert result.metrics["observations"] == 180
    assert result.metrics["r_squared"] == pytest.approx(expected.rsquared)
    assert result.metrics["alpha_annual_arithmetic"] == pytest.approx(12 * expected.params.iloc[0])
    np.testing.assert_allclose(result.fitted + result.residuals, returns - factors.RF)
    assert len(result.rolling) == 145
    np.testing.assert_allclose(
        result.rolling.iloc[-1],
        sm.OLS((returns - factors.RF).iloc[-36:], x.iloc[-36:]).fit().params,
    )
    assert all(np.isfinite(list(result.diagnostics.values())))


@pytest.mark.parametrize("model", MODELS)
def test_recovers_known_coefficients(model):
    _, factors = demo_data()
    betas = np.arange(1, len(MODELS[model]) + 1) * 0.15
    rng = np.random.default_rng(1)
    returns = (
        factors.RF + 0.002 + factors[MODELS[model]] @ betas + rng.normal(0, 0.0001, len(factors))
    )
    result = fit_model(returns, factors, model)
    np.testing.assert_allclose(result.coefficients.coefficient, [0.002, *betas], atol=0.002)


@pytest.mark.parametrize(
    "case,match",
    [
        ("short", "24 meses"),
        ("missing", "Fatores ausentes"),
        ("duplicate_returns", "duplicados"),
        ("duplicate_factors", "duplicados"),
        ("gap", "meses ausentes"),
        ("infinity", "finitos"),
        ("bad_return", "100%"),
        ("singular", "singular"),
        ("date", "fim do mês"),
        ("nat", "Datas ausentes"),
    ],
)
def test_invalid_inputs(case, match):
    returns, factors = demo_data()
    if case == "short":
        returns = returns.iloc[:23]
    elif case == "missing":
        factors = factors.drop(columns="RF")
    elif case == "duplicate_returns":
        returns = pd.concat([returns, returns.iloc[:1]])
    elif case == "duplicate_factors":
        factors = pd.concat([factors, factors.iloc[:1]])
    elif case == "gap":
        returns = returns.drop(returns.index[40])
    elif case == "infinity":
        returns.iloc[0] = np.inf
    elif case == "bad_return":
        returns.iloc[0] = -1.1
    elif case == "singular":
        factors["HML"] = factors["SMB"]
    elif case == "date":
        returns.index = returns.index - pd.Timedelta(days=1)
    elif case == "nat":
        returns.index = pd.DatetimeIndex([pd.NaT, *returns.index[1:]])
    with pytest.raises(ValueError, match=match):
        fit_model(returns, factors)


@pytest.mark.parametrize(
    "kwargs", [{"model": "INVALID"}, {"hac_lags": -1}, {"hac_lags": 180}, {"rolling_window": 2}]
)
def test_invalid_configuration(kwargs):
    with pytest.raises(ValueError):
        fit_model(*demo_data(), **kwargs)


def test_index_type_and_insufficient_rolling():
    returns, factors = demo_data()
    assert fit_model(returns.iloc[:24], factors).rolling.empty
    returns.index = pd.RangeIndex(len(returns))
    with pytest.raises(TypeError):
        fit_model(returns, factors)


def test_aligns_sorts_and_drops_boundary_nan():
    returns, factors = demo_data()
    returns.iloc[0] = np.nan
    result = fit_model(returns.iloc[::-1], factors.iloc[10:])
    assert len(result.data) == 170
    assert result.data.index.is_monotonic_increasing
