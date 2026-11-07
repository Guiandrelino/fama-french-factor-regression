import pandas as pd

from factorlab.data import demo_data
from factorlab.regression import fit_model
from ui.components import br_number, percent


def test_brazilian_formatting_does_not_mutate_values():
    assert br_number(1234.56) == "1.234,56"
    assert percent(-0.025) == "-2,50%"
    assert br_number(float("nan")) == "—"
    returns, factors = demo_data()
    original = returns.copy()
    result = fit_model(returns, factors, "FF5")
    before = result.coefficients.copy()
    result.coefficients.coefficient.map(br_number)
    pd.testing.assert_frame_equal(before, result.coefficients)
    pd.testing.assert_series_equal(original, returns)
