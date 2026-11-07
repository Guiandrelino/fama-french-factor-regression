import io
import zipfile

import numpy as np
import pandas as pd
import pytest

from factorlab.data import monthly_returns, parse_french_zip, read_returns_csv


def test_french_parser_percentages_and_annual_section():
    text = (
        "Notes\n,Mkt-RF,SMB,HML,RF\n"
        "202001,1.20,2.00,-3.00,0.10\n"
        "202002,-99.99,0,0,0.12\n\nAnnual Factors\n2020,12,1,1,1\n"
    )
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w") as archive:
        archive.writestr("factors.csv", text)
    result = parse_french_zip(buffer.getvalue())
    assert len(result) == 2
    assert result.iloc[0]["Mkt-RF"] == pytest.approx(0.012)
    assert result.iloc[0]["RF"] == pytest.approx(0.001)
    assert np.isnan(result.iloc[1]["Mkt-RF"])
    assert result.index[0] == pd.Timestamp("2020-01-31")


def test_monthly_returns_do_not_fill_missing_months():
    prices = pd.Series(
        [100, 110, 120, 132],
        index=pd.to_datetime(["2020-01-31", "2020-02-28", "2020-04-30", "2020-05-29"]),
    )
    result = monthly_returns(prices)
    assert list(result.index.month) == [2, 5]
    np.testing.assert_allclose(result, [0.1, 0.1])


def test_current_month_is_excluded():
    current = pd.Timestamp.today().normalize()
    previous = current.to_period("M").to_timestamp() - pd.Timedelta(days=1)
    older = previous.to_period("M").to_timestamp() - pd.Timedelta(days=1)
    import pandas_market_calendars as mcal

    sessions = mcal.get_calendar("NYSE").schedule(
        start_date=older.to_period("M").start_time, end_date=previous
    )
    ends = pd.Series(sessions.index, index=sessions.index).resample("ME").last()
    result = monthly_returns(pd.Series([100, 110, 150], index=[*ends, current]))
    assert len(result) == 1
    assert result.iloc[0] == pytest.approx(0.1)


def test_csv_normalizes_dates():
    result = read_returns_csv(io.StringIO("date,return\n2020-01-01,0.02\n2020-02-15,-0.01\n"))
    assert result.index[0] == pd.Timestamp("2020-01-31")
    assert result.iloc[0] == 0.02


@pytest.mark.parametrize(
    "text",
    [
        "date,return\n2020-01-01,0.1\n2020-01-31,0.2\n",
        "date,return\n2020-01-01,-1.1\n",
        "date,return\n2020-01-01,inf\n",
        "date,price\n2020-01-01,100\n",
        "date,return\n,0.1\n",
        "date,return\n",
        "date,return\nnot-a-date,0.1\n",
    ],
)
def test_invalid_csv(text):
    with pytest.raises(ValueError):
        read_returns_csv(io.StringIO(text))
