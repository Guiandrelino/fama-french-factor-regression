"""Contexto de usuário explícito, locks de arquivos e gravações atômicas."""

import os
import tempfile
from contextlib import contextmanager
from pathlib import Path

from filelock import FileLock


def workspace_root():
    import hashlib

    import streamlit as st

    user = st.session_state.get("authenticated_user", "local")
    if os.getenv("FACTORLAB_PUBLIC") == "1" and user == "local":
        raise PermissionError("Workspace privado exige autenticação.")
    identifier = hashlib.sha256(user.encode()).hexdigest()
    root = Path(os.getenv("FACTORLAB_DATA_DIR", ".cache")) / "users" / identifier
    root.mkdir(parents=True, exist_ok=True, mode=0o700)
    return root


@contextmanager
def path_lock(path):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with FileLock(str(path) + ".lock", timeout=30):
        yield


def enforce_quota(root, additional=0):
    limit = int(os.getenv("FACTORLAB_QUOTA_MB", "250")) * 1024 * 1024
    used = sum(p.stat().st_size for p in Path(root).rglob("*") if p.is_file())
    if used + additional > limit:
        raise ValueError(
            "Quota de armazenamento excedida; exclua análises/snapshots ou contate o administrador."
        )


def atomic_write(path, content):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    fd, temporary = tempfile.mkstemp(dir=path.parent, prefix=".pending-")
    try:
        with os.fdopen(fd, "wb") as stream:
            stream.write(content)
        os.replace(temporary, path)
    finally:
        Path(temporary).unlink(missing_ok=True)
