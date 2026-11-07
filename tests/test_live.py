"""Smoke tests reais; execução explícita: pytest -m live."""

import numpy as np
import pytest

from factorlab.data import load_factors, load_prices, monthly_returns
from factorlab.regression import fit_model

pytestmark = pytest.mark.live


@pytest.fixture(scope="module", params=["SPY", "AAPL", "MSFT", "IWM"])
def asset_returns(request):
    return monthly_returns(load_prices(request.param, "2015-01-01", "2025-01-01"))


@pytest.mark.parametrize("model", ["CAPM", "FF3", "FF5", "CARHART4", "FF6"])
def test_real_asset(asset_returns, model):
    returns = asset_returns
    result = fit_model(returns, load_factors(model), model=model)
    assert result.metrics["observations"] >= 110
    assert np.isfinite(result.coefficients.to_numpy()).all()
    assert 0 <= result.metrics["r_squared"] <= 1
    assert result.data.index.max().year == 2024
