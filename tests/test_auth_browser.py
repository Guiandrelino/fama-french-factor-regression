"""Duas sessões reais: login, expiração/logout e isolamento SQLite."""

import json
import os
import socket
import subprocess
import sys
import time
import urllib.request
from pathlib import Path

import pytest

from factorlab.security import password_hash

pytestmark = pytest.mark.browser
ROOT = Path(__file__).resolve().parents[1]


def test_two_users_isolated(tmp_path):
    from playwright.sync_api import sync_playwright

    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        port = sock.getsockname()[1]
    env = {
        **os.environ,
        "FACTORLAB_USERS_JSON": json.dumps(
            {"alice": password_hash("alice-pass"), "bob": password_hash("bob-pass")}
        ),
        "FACTORLAB_PUBLIC": "1",
        "FACTORLAB_DATA_DIR": str(tmp_path / "private"),
    }
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
            env=env,
            cwd=tmp_path,
            stdout=log,
            stderr=log,
        )
        try:
            url = f"http://localhost:{port}"
            for _ in range(100):
                try:
                    urllib.request.urlopen(url + "/_stcore/health", timeout=1).close()
                    break
                except OSError:
                    time.sleep(0.2)
            with sync_playwright() as p:
                browser = p.chromium.launch()
                contexts = [browser.new_context(), browser.new_context()]
                pages = [c.new_page() for c in contexts]
                for page, user in zip(pages, ["alice", "bob"], strict=True):
                    page.goto(url + "/Pesquisa")
                    page.get_by_label("Usuário", exact=True).fill(user)
                    page.get_by_label("Senha", exact=True).fill(user + "-pass")
                    page.get_by_role("button", name="Entrar", exact=True).click()
                    page.get_by_text("Demonstração", exact=True).click()
                    page.get_by_role("button", name="Executar pesquisa", exact=True).click()
                    page.get_by_text("RISCO E CARTEIRA", exact=True).wait_for(timeout=60000)
                alice, bob = pages
                alice.get_by_text("RISCO E CARTEIRA", exact=True).click()
                alice.get_by_role("tab", name="03 · Análises salvas").click()
                alice.get_by_label("Nome da análise", exact=True).fill("ALICE PRIVATE")
                alice.get_by_role("button", name="Salvar análise local", exact=True).click()
                alice.get_by_text("Análise salva:", exact=False).wait_for()
                bob.get_by_text("RISCO E CARTEIRA", exact=True).click()
                bob.get_by_role("tab", name="03 · Análises salvas").click()
                assert bob.get_by_text("ALICE PRIVATE", exact=True).count() == 0
                alice.get_by_role("button", name="Encerrar sessão").click()
                alice.get_by_role("button", name="Entrar", exact=True).wait_for()
                assert alice.get_by_text("ALICE PRIVATE", exact=True).count() == 0
                assert bob.get_by_role("button", name="Encerrar sessão").count() == 1
                browser.close()
        finally:
            server.terminate()
            server.wait(timeout=20)
