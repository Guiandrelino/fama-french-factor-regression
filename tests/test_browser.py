"""Upload real no Chromium. Não usa monkeypatch no widget ou na aplicação."""

import io
import os
import socket
import subprocess
import time
import urllib.request
import zipfile
from pathlib import Path

import pytest

from factorlab.data import demo_data

pytestmark = pytest.mark.browser
ROOT = Path(__file__).resolve().parents[1]


def test_csv_upload_and_download_in_browser(tmp_path):
    from playwright.sync_api import sync_playwright

    # Servidor isolado usa fatores sintéticos em cache; não requer internet.
    returns, factors = demo_data()
    cache = tmp_path / ".cache"
    cache.mkdir()
    text = io.StringIO()
    (factors * 100).set_axis(factors.index.strftime("%Y%m")).to_csv(text)
    for family in ["FF3", "FF5"]:
        with zipfile.ZipFile(cache / f"{family}.zip", "w") as archive:
            archive.writestr("factors.csv", text.getvalue())
    panel_csv = tmp_path / "panel.csv"
    pd_panel = returns.to_frame("AAPL")
    pd_panel["MSFT"] = returns * 0.8
    pd_panel["SPY"] = returns * 0.9
    pd_panel["IWM"] = returns * 1.1
    pd_panel.rename_axis("date").to_csv(panel_csv)
    csv = tmp_path / "returns.csv"
    returns.rename("return").rename_axis("date").to_csv(csv)
    bad_csv = tmp_path / "bad.csv"
    bad_csv.write_text("date,price\n2020-01-01,100\n", encoding="utf-8")
    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        port = sock.getsockname()[1]
    import sys

    env = {**os.environ, "STREAMLIT_BROWSER_GATHER_USAGE_STATS": "false"}
    with (tmp_path / "server.log").open("w") as log:
        server = subprocess.Popen(
            [
                sys.executable,
                "-m",
                "streamlit",
                "run",
                str(ROOT / "app.py"),
                "--server.headless=true",
                f"--server.port={port}",
            ],
            cwd=tmp_path,
            env=env,
            stdout=log,
            stderr=log,
        )
        try:
            url = f"http://localhost:{port}"
            for _ in range(100):
                try:
                    with urllib.request.urlopen(url + "/_stcore/health", timeout=1) as response:
                        if response.status == 200:
                            break
                except OSError:
                    time.sleep(0.2)
            else:
                pytest.fail("Dashboard não iniciou")
            with sync_playwright() as p:
                browser = p.chromium.launch()
                page = browser.new_page(accept_downloads=True)
                page.goto(url)
                page.get_by_text("CSV próprio", exact=True).click()
                page.locator('input[type="file"]').set_input_files(str(csv))
                page.get_by_text("returns.csv", exact=True).wait_for()
                page.get_by_role("button", name="Executar análise").click()
                page.get_by_text("Alpha mensal", exact=True).wait_for(timeout=30000)
                page.get_by_role("tab", name="Dados e exportação").click()
                with page.expect_download() as download:
                    page.get_by_text("Baixar coefficients.csv", exact=True).click()
                exported = tmp_path / "download.csv"
                download.value.save_as(exported)
                assert "alpha" in exported.read_text()
                assert "std_error_HAC" in exported.read_text()
                page.locator('input[type="file"]').set_input_files(str(bad_csv))
                page.get_by_text("bad.csv", exact=True).wait_for()
                # Upload e download podem disparar reruns assíncronos no Streamlit.
                # Espere o rerun terminar antes de enviar um novo evento de botão.
                page.locator('[data-testid="stStatusWidget"]').wait_for(state="hidden")
                from playwright.sync_api import TimeoutError as PlaywrightTimeoutError

                error = page.get_by_text("CSV deve conter as colunas date e return.", exact=False)
                for attempt in range(3):
                    page.get_by_role("button", name="Executar análise").click()
                    try:
                        error.wait_for(timeout=10000)
                        break
                    except PlaywrightTimeoutError:
                        if attempt == 2:
                            page.screenshot(path=str(tmp_path / "upload-failure.png"))
                            raise
                assert page.get_by_text("Alpha mensal", exact=True).count() == 0
                page.goto(url + "/Pesquisa")
                page.get_by_text("CSV de retornos", exact=True).click()
                page.locator('input[type="file"]').set_input_files(str(panel_csv))
                page.get_by_text("panel.csv", exact=True).wait_for()
                page.get_by_role("button", name="Executar pesquisa", exact=True).click()
                page.get_by_role("tab", name="Relatório e exportação").wait_for(timeout=60000)
                page.get_by_role("tab", name="Relatório e exportação").click()
                with page.expect_download() as bundle:
                    page.get_by_text("Baixar pacote consolidado ZIP", exact=True).click()
                bundle_path = tmp_path / "bundle.zip"
                bundle.value.save_as(bundle_path)
                with zipfile.ZipFile(bundle_path) as archive:
                    assert "report.html" in archive.namelist()
                    assert "Carteira" in archive.read("summary.csv").decode()
                browser.close()
        finally:
            server.terminate()
            server.wait(timeout=20)
