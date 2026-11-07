"""Snapshots e manifesto reprodutível, sem sobrescrever versões anteriores."""

import hashlib
import importlib.metadata
import json
from datetime import UTC, datetime
from pathlib import Path

import pandas as pd


def snapshot(content: bytes, source: str, root: str | Path = ".cache") -> dict:
    import os

    if os.getenv("FACTORLAB_USERS_JSON"):
        from factorlab.security import workspace_root

        root = workspace_root()
    digest = hashlib.sha256(content).hexdigest()
    path = Path(root) / "snapshots" / digest
    path.parent.mkdir(parents=True, exist_ok=True)
    from factorlab.runtime import atomic_write, enforce_quota, path_lock

    with path_lock(Path(root) / "quota"):
        if not path.exists():
            enforce_quota(root, len(content))
            atomic_write(path, content)
    return {
        "source": source,
        "sha256": digest,
        "snapshot": str(path),
        "retrieved_at": datetime.now(UTC).isoformat(),
        "bytes": len(content),
    }


def frame_record(frame: pd.DataFrame, name: str, root: str | Path = ".cache") -> dict:
    record = snapshot(frame.to_csv(float_format="%.17g").encode(), name, root)
    record.update(
        {"rows": len(frame), "start": str(frame.index.min()), "end": str(frame.index.max())}
    )
    return record


def manifest(
    parameters: dict, frames: dict[str, pd.DataFrame], root: str | Path = ".cache"
) -> dict:
    versions = {
        name: importlib.metadata.version(name)
        for name in ["factorlab", "numpy", "pandas", "statsmodels", "pandas-market-calendars"]
    }
    return {
        "schema_version": 1,
        "created_at": datetime.now(UTC).isoformat(),
        "parameters": parameters,
        "versions": versions,
        "inputs": {
            name: {
                "data": frame_record(frame, name, root),
                "upstream": frame.attrs.get("provenance", {}),
            }
            for name, frame in frames.items()
        },
    }


def cache_status(root: str | Path = ".cache", max_age_days: int = 7) -> list[dict]:
    records = []
    for path in sorted(Path(root).glob("*.meta.json")):
        metadata = json.loads(path.read_text(encoding="utf-8"))
        age = (datetime.now(UTC) - datetime.fromisoformat(metadata["retrieved_at"])).days
        records.append({**metadata, "age_days": age, "stale": age >= max_age_days})
    return records
