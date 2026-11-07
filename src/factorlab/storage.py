"""Análises locais em SQLite; somente JSON/CSV, nunca pickle executável."""

import io
import json
import sqlite3
from contextlib import contextmanager
from datetime import UTC, datetime
from pathlib import Path

import pandas as pd


class AnalysisStore:
    def __init__(self, path=".cache/analyses.sqlite"):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self.connect() as conn:
            conn.execute("""CREATE TABLE IF NOT EXISTS analyses (
                id INTEGER PRIMARY KEY, name TEXT NOT NULL, created_at TEXT NOT NULL,
                metadata TEXT NOT NULL, summary TEXT NOT NULL, returns_csv TEXT NOT NULL)""")

    @contextmanager
    def connect(self):
        conn = sqlite3.connect(self.path, timeout=15)
        try:
            with conn:
                yield conn
        finally:
            conn.close()

    def save(self, name, study, metadata):
        if not name.strip() or len(name) > 120:
            raise ValueError("Nome obrigatório, até 120 caracteres.")
        with self.connect() as conn:
            cursor = conn.execute(
                "INSERT INTO analyses(name,created_at,metadata,summary,returns_csv) VALUES(?,?,?,?,?)",
                (
                    name.strip(),
                    datetime.now(UTC).isoformat(),
                    json.dumps(metadata, ensure_ascii=False),
                    study.summary.to_json(orient="table"),
                    study.returns.to_csv(),
                ),
            )
            return cursor.lastrowid

    def list(self):
        with self.connect() as conn:
            return pd.read_sql_query(
                "SELECT id,name,created_at FROM analyses ORDER BY id DESC", conn
            )

    def load(self, analysis_id):
        with self.connect() as conn:
            row = conn.execute(
                "SELECT name,metadata,summary,returns_csv FROM analyses WHERE id=?",
                (int(analysis_id),),
            ).fetchone()
        if row is None:
            raise ValueError("Análise não encontrada.")
        return {
            "name": row[0],
            "metadata": json.loads(row[1]),
            "summary": pd.read_json(io.StringIO(row[2]), orient="table"),
            "returns": pd.read_csv(io.StringIO(row[3]), index_col=0, parse_dates=True),
        }

    def delete(self, analysis_id):
        with self.connect() as conn:
            conn.execute("DELETE FROM analyses WHERE id=?", (int(analysis_id),))


def compare_saved(first, second):
    a, b = first["summary"], second["summary"]
    index = a.index.intersection(b.index)
    columns = a.select_dtypes("number").columns.intersection(b.select_dtypes("number").columns)
    if index.empty:
        raise ValueError("Análises sem ativos/modelos em comum.")
    # Diferença descritiva: amostras distintas não são teste de melhora estatística.
    return b.loc[index, columns] - a.loc[index, columns]
