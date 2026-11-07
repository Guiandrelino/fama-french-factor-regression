"""Autenticação por hashes PBKDF2 e diretórios isolados. Segredos via ambiente."""

import hashlib
import hmac
import json
import os
import secrets
import sqlite3
from contextlib import closing
from pathlib import Path

import streamlit as st


def password_hash(password, salt=None):
    salt = salt or secrets.token_hex(16)
    digest = hashlib.pbkdf2_hmac("sha256", password.encode(), salt.encode(), 600_000).hex()
    return f"{salt}${digest}"


def verify_password(password, encoded):
    try:
        salt, _ = encoded.split("$")
        return hmac.compare_digest(password_hash(password, salt), encoded)
    except (ValueError, AttributeError):
        return False


def user_root(user):
    identifier = hashlib.sha256(user.encode()).hexdigest()
    root = Path(os.getenv("FACTORLAB_DATA_DIR", ".cache")) / "users" / identifier
    root.mkdir(parents=True, exist_ok=True, mode=0o700)
    return root


def workspace_root():
    # Fora de uma sessão autenticada, usa somente o workspace local.
    return user_root(st.session_state.get("authenticated_user", "local"))


def require_login():
    encoded = os.getenv("FACTORLAB_USERS_JSON", "")
    public = os.getenv("FACTORLAB_PUBLIC", "0") == "1"
    if not encoded:
        if public:
            st.error("Publicação bloqueada: configure FACTORLAB_USERS_JSON e HTTPS.")
            st.stop()
        st.caption("LOCAL WORKSPACE · autenticação desativada · não exponha publicamente")
        return
    users = json.loads(encoded)
    import time

    attempts = st.session_state.get("login_attempts", 0)
    if attempts >= 5 and time.time() - st.session_state.get("last_login_attempt", 0) < 60:
        st.error("Muitas tentativas nesta sessão. Aguarde um minuto.")
        st.stop()
    if st.session_state.get("authenticated_user") not in users:
        with st.form("login"):
            user = st.text_input("Usuário")
            password = st.text_input("Senha", type="password")
            submit = st.form_submit_button("Entrar")
        if submit:
            if verify_password(password, users.get(user, "invalid")):
                st.session_state.clear()
                st.session_state["authenticated_user"] = user
                st.rerun()
            st.session_state["login_attempts"] = attempts + 1
            st.session_state["last_login_attempt"] = time.time()
            st.error("Credenciais inválidas.")
        st.stop()
    if st.sidebar.button("Encerrar sessão"):
        st.session_state.clear()
        st.rerun()


def backup_database(path):
    source = sqlite3.connect(path)
    destination = Path(path).with_suffix(".backup.sqlite")
    try:
        with closing(sqlite3.connect(destination)) as target:
            source.backup(target)
    finally:
        source.close()
    return destination.read_bytes()


def restore_database(path, content):
    if not content.startswith(b"SQLite format 3\x00") or len(content) > 25_000_000:
        raise ValueError("Backup SQLite inválido ou maior que 25 MB.")
    temporary = Path(path).with_suffix(".restore.sqlite")
    temporary.write_bytes(content)
    try:
        with closing(sqlite3.connect(temporary)) as conn:
            if conn.execute("PRAGMA integrity_check").fetchone()[0] != "ok":
                raise ValueError("Backup corrompido.")
            required = {"id", "name", "created_at", "metadata", "summary", "returns_csv"}
            if not required.issubset({r[1] for r in conn.execute("PRAGMA table_info(analyses)")}):
                raise ValueError("Esquema de backup incompatível.")
        os.replace(temporary, path)
    finally:
        temporary.unlink(missing_ok=True)


def purge_snapshots(root, days=30):
    import time

    if days < 1:
        raise ValueError("Retenção mínima de um dia.")
    count = 0
    for path in (Path(root) / "snapshots").glob("*"):
        if path.is_file() and path.stat().st_mtime < time.time() - days * 86400:
            path.unlink()
            count += 1
    return count
