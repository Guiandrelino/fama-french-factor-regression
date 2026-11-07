import io
import json
import zipfile

import pandas as pd
import pytest
import requests

from factorlab.cli import main
from factorlab.data import load_factors, load_prices, parse_french_zip


@pytest.mark.parametrize("text", ["notes", ",Mkt-RF,RF\nannual\n"])
def test_invalid_factor_header_or_rows(text):
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w") as archive:
        archive.writestr("f.csv", text)
    with pytest.raises(ValueError):
        parse_french_zip(buffer.getvalue())


def test_factor_cache_and_refresh(tmp_path, monkeypatch):
    calls = []
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w") as archive:
        archive.writestr("f.csv", ",Mkt-RF,RF\n202001,1,0.1\n")

    class Response:
        content = buffer.getvalue()

        def raise_for_status(self):
            pass

    def get(*args, **kwargs):
        calls.append(args)
        return Response()

    monkeypatch.setattr("factorlab.data.requests.get", get)
    first = load_factors("CAPM", tmp_path)
    pd.testing.assert_frame_equal(first, load_factors("FF3", tmp_path))
    assert len(calls) == 1
    load_factors("FF3", tmp_path, refresh=True)
    assert len(calls) == 2
    with pytest.raises(ValueError):
        load_factors("INVALID", tmp_path)


def test_network_failure_does_not_create_cache(tmp_path, monkeypatch):
    def fail(*args, **kwargs):
        raise requests.Timeout("timeout")

    monkeypatch.setattr("factorlab.data.requests.get", fail)
    with pytest.raises(requests.Timeout):
        load_factors(cache_dir=tmp_path)
    assert not list(tmp_path.iterdir())


def test_empty_price_source(monkeypatch):
    monkeypatch.setattr("factorlab.data.yf.download", lambda *a, **k: pd.DataFrame())
    with pytest.raises(ValueError, match="Sem preços"):
        load_prices("SPY", "2020-01-01", None)
    with pytest.raises(ValueError, match="único ticker"):
        load_prices("", "2020-01-01", None)


def test_cli_exports(tmp_path, monkeypatch):
    monkeypatch.setattr("sys.argv", ["factorlab", "--demo", "--output", str(tmp_path)])
    main()
    assert len(pd.read_csv(tmp_path / "observations.csv")) == 180
    report = json.loads((tmp_path / "report.json").read_text())
    assert report["source"] == "synthetic"
    assert report["metrics"]["observations"] == 180
    assert (tmp_path / "rolling.csv").exists()


def test_cli_failure(monkeypatch, tmp_path):
    monkeypatch.setattr("sys.argv", ["factorlab", "--csv", str(tmp_path / "missing.csv")])
    with pytest.raises(SystemExit) as exc:
        main()
    assert exc.value.code == 1
