"""Auditoria sem correção implícita de observações."""

from datetime import UTC, datetime

import numpy as np
import pandas as pd
import pandas_market_calendars as mcal


def audit_panel(panel, factors, currency, source, threshold=0.25):
    if panel.empty or panel.index.has_duplicates:
        raise ValueError("Painel vazio ou datas duplicadas.")
    expected = pd.date_range(panel.index.min(), panel.index.max(), freq="ME")
    common = panel.dropna().index
    for frame in factors.values():
        common = common.intersection(frame.dropna().index)
    rows, extreme = [], []
    for asset in panel:
        series = panel[asset].reindex(expected)
        valid = series.dropna()
        missing = series.index[series.isna()]
        rows.append(
            {
                "asset": asset,
                "currency": currency,
                "source": source,
                "audited_at": datetime.now(UTC).isoformat(),
                "available": len(valid),
                "common_months": len(common),
                "discarded": len(valid) - len(common),
                "missing_months": ", ".join(missing.strftime("%Y-%m")),
                "first": str(valid.index.min()),
                "last": str(valid.index.max()),
                "status": "erro"
                if len(missing) or not np.isfinite(valid).all() or (valid < -1).any()
                else "disponível",
            }
        )
        for date, value in valid[valid.abs() > threshold].items():
            extreme.append({"asset": asset, "date": date, "return": value})
    return pd.DataFrame(rows), pd.DataFrame(extreme, columns=["asset", "date", "return"]), common


def calendar_audit(prices, calendar="NYSE"):
    schedule = mcal.get_calendar(calendar).schedule(
        start_date=prices.index.min(), end_date=prices.index.max().to_period("M").end_time
    )
    expected = pd.DatetimeIndex(schedule.index).normalize()
    actual = pd.DatetimeIndex(prices.dropna().index).normalize()
    return pd.DataFrame({"missing_session": expected.difference(actual)})


def source_health(provenance, max_days=7):
    rows = []

    def visit(key, value):
        if isinstance(value, dict) and "retrieved_at" in value:
            age = (
                datetime.now(UTC) - datetime.fromisoformat(value["retrieved_at"])
            ).total_seconds() / 86400
            rows.append(
                {
                    "source": key,
                    "updated_at": value["retrieved_at"],
                    "age_days": age,
                    "status": "desatualizada" if age >= max_days else "disponível",
                }
            )
        elif isinstance(value, dict):
            for name, nested in value.items():
                visit(name, nested)

    visit("input", provenance)
    return pd.DataFrame(rows)
