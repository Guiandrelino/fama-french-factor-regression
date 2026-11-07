from pathlib import Path

import pytest
from streamlit.testing.v1 import AppTest

from factorlab.providers import load_nefin


@pytest.mark.parametrize("policy", ["monthly", "buy_hold"])
def test_workspace_demo(policy):
    app = AppTest.from_file(
        str(Path(__file__).parents[1] / "pages/2_Pesquisa.py"), default_timeout=40
    ).run()
    app.sidebar.radio[0].set_value("Demonstração").run()
    app.sidebar.selectbox[1].set_value(policy)
    app.sidebar.button[0].click().run()
    assert not app.exception
    assert not app.error
    study, metadata, extras, oos = app.session_state["study"]
    assert "Carteira" in study.returns
    assert metadata["parameters"]["policy"] == policy
    assert len(study.results) == 10
    assert len(oos) == 10
    assert extras


def test_nefin_monthly_decimal_parser(monkeypatch, tmp_path):
    raw = (
        b"year,month,Rm_minus_Rf,SMB,HML,WML,IML,Risk_Free\n2020,1,0.02,0.01,-0.01,0.03,0.0,0.005\n"
    )
    monkeypatch.setattr(
        "factorlab.providers.cached_download", lambda *a: (raw, {"source": "fixture"})
    )
    result = load_nefin(tmp_path)
    assert result.index[0].day == 31
    assert result.iloc[0].RF == 0.005
    assert result.iloc[0].Mom == 0.03
