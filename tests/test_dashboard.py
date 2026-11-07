from pathlib import Path

import pytest
from streamlit.testing.v1 import AppTest

APP = str(Path(__file__).resolve().parents[1] / "app.py")


@pytest.mark.parametrize("model", ["CAPM", "FF3", "FF5"])
def test_demo_dashboard(model):
    app = AppTest.from_file(APP, default_timeout=20).run()
    app.sidebar.selectbox[0].select(model)
    app.sidebar.button[0].click().run(timeout=30)
    assert not app.exception
    assert not app.error
    assert len(app.metric) == 4
    assert len(app.dataframe) == 3
    assert app.warning


def test_csv_without_upload_and_invalid_dates():
    app = AppTest.from_file(APP, default_timeout=20).run()
    app.sidebar.radio[0].set_value("CSV próprio").run()
    app.sidebar.button[0].click().run()
    assert "Envie um CSV" in app.error[0].value
    assert not app.exception
    app.sidebar.date_input[0].set_value(app.sidebar.date_input[1].value).run()
    app.sidebar.button[0].click().run()
    assert "data inicial" in app.error[0].value
    assert not app.exception


def test_network_error_shown_without_stale_results(monkeypatch):
    import factorlab.data

    app = AppTest.from_file(APP, default_timeout=20).run()
    app.sidebar.button[0].click().run()
    assert app.metric

    def fail(*args, **kwargs):
        raise ConnectionError("Fonte indisponível")

    monkeypatch.setattr(factorlab.data, "load_prices", fail)
    app.sidebar.radio[0].set_value("Yahoo Finance").run()
    app.sidebar.text_input[0].set_value("NETWORK_TEST")
    app.sidebar.button[0].click().run()
    assert "Fonte indisponível" in app.error[0].value
    assert not app.metric
    assert not app.exception
