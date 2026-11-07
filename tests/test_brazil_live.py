import pytest

from factorlab.data import load_prices, monthly_returns
from factorlab.providers import load_nefin
from factorlab.regression import fit_model


@pytest.mark.live
@pytest.mark.parametrize("model", ["CAPM", "FF3", "CARHART4"])
def test_brazil_nefin_bova(model):
    # Período posterior ao gap do Yahoo em dezembro/2017.
    returns = monthly_returns(load_prices("BOVA11.SA", "2019-01-01", "2025-01-01"), "BMF")
    result = fit_model(returns, load_nefin(), model)
    assert result.metrics["observations"] >= 60
