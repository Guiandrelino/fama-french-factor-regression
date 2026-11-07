"""Fontes externas e validação: fatores em decimais, datas no fim do mês."""

from __future__ import annotations

import io
import json
import time
import zipfile
from pathlib import Path

import numpy as np
import pandas as pd
import pandas_market_calendars as mcal
import requests
import yfinance as yf

from factorlab.provenance import snapshot

FACTOR_URLS = {
    "FF3": "https://mba.tuck.dartmouth.edu/pages/faculty/ken.french/ftp/F-F_Research_Data_Factors_CSV.zip",
    "FF5": "https://mba.tuck.dartmouth.edu/pages/faculty/ken.french/ftp/F-F_Research_Data_5_Factors_2x3_CSV.zip",
}


def month_index(values) -> pd.DatetimeIndex:
    dates = pd.DatetimeIndex(pd.to_datetime(values, errors="raise", utc=True)).tz_convert(None)
    if dates.hasnans:
        raise ValueError("Datas ausentes não são permitidas.")
    return dates.to_period("M").to_timestamp("M")


def parse_french_zip(content: bytes, header_key: str = "Mkt-RF") -> pd.DataFrame:
    """Lê apenas o bloco mensal YYYYMM; ignora notas e bloco anual."""
    with zipfile.ZipFile(io.BytesIO(content)) as archive:
        names = [n for n in archive.namelist() if n.lower().endswith(".csv")]
        if not names:
            raise ValueError("Arquivo Kenneth French sem CSV.")
        text = archive.read(names[0]).decode("utf-8-sig")
    lines = text.splitlines()
    header = next(
        (i for i, line in enumerate(lines) if line.strip().startswith(",") and header_key in line),
        None,
    )
    if header is None:
        raise ValueError("Cabeçalho de fatores não encontrado.")
    rows = []
    for line in lines[header + 1 :]:
        date = line.split(",")[0].strip()
        if len(date) == 6 and date.isdigit():
            rows.append(line)
        elif rows:
            break
    if not rows:
        raise ValueError("Nenhuma observação mensal encontrada.")
    df = pd.read_csv(io.StringIO("\n".join([lines[header], *rows])), index_col=0)
    df.columns = df.columns.str.strip()
    df.index = pd.to_datetime(df.index.astype(str), format="%Y%m").to_period("M").to_timestamp("M")
    df.index.name = "date"
    df = df.apply(pd.to_numeric, errors="raise")
    # Sentinelas da biblioteca, antes da conversão de percentual para decimal.
    df = df.mask(df.isin([-99.99, -999])) / 100
    return df.sort_index()


def cached_download(url, filename, cache_dir=".cache", refresh=False):
    path = Path(cache_dir) / filename
    meta_path = path.with_suffix(path.suffix + ".meta.json")
    if path.exists() and not refresh:
        raw = path.read_bytes()
        metadata = (
            json.loads(meta_path.read_text(encoding="utf-8"))
            if meta_path.exists()
            else snapshot(raw, url, cache_dir)
        )
        if not meta_path.exists():
            metadata["timestamp_note"] = "Cache legado: data de registro, não de download."
            meta_path.write_text(json.dumps(metadata), encoding="utf-8")
        return raw, metadata
    response = requests.get(url, timeout=60)
    response.raise_for_status()
    raw = response.content
    metadata = snapshot(raw, url, cache_dir)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(raw)
    meta_path.write_text(json.dumps(metadata), encoding="utf-8")
    return raw, metadata


def load_factors(
    model: str = "FF5", cache_dir: str | Path = ".cache", refresh: bool = False
) -> pd.DataFrame:
    if model not in {"CAPM", "FF3", "FF5", "CARHART4", "FF6"}:
        raise ValueError("Modelo inválido.")
    family = "FF3" if model in {"CAPM", "FF3", "CARHART4"} else "FF5"
    raw, meta = cached_download(FACTOR_URLS[family], f"{family}.zip", cache_dir, refresh)
    df = parse_french_zip(raw)
    provenance = {family: meta}
    if model in {"CARHART4", "FF6"}:
        url = "https://mba.tuck.dartmouth.edu/pages/faculty/ken.french/ftp/F-F_Momentum_Factor_CSV.zip"
        raw, meta = cached_download(url, "momentum.zip", cache_dir, refresh)
        df = df.join(parse_french_zip(raw, "Mom"), how="inner")
        provenance["momentum"] = meta
    df.attrs["provenance"] = provenance
    return df


def download_prices_with_retry(ticker, start, end, attempts=3, delay=1):
    """Retenta falhas transitórias sem trocar silenciosamente a fonte ou usar cache antigo."""
    last_error = None
    for attempt in range(attempts):
        try:
            frame = yf.download(
                ticker,
                start=start,
                end=end,
                auto_adjust=True,
                progress=False,
                threads=False,
                timeout=20,
            )
            if not frame.empty:
                return frame
        except Exception as exc:
            last_error = exc
        if attempt + 1 < attempts:
            time.sleep(delay * 2**attempt)
    if last_error is not None:
        raise ConnectionError(
            f"Yahoo indisponível após {attempts} tentativas: {ticker}"
        ) from last_error
    return pd.DataFrame()


def load_prices(
    ticker: str, start: str, end: str | None, refresh=False, cache_ttl=3600
) -> pd.Series:
    """Download diário ajustado. `end` é exclusivo, conforme API Yahoo."""
    ticker = ticker.strip().upper()
    if not ticker or len(ticker.split()) != 1:
        raise ValueError("Informe um único ticker dos EUA, como AAPL ou SPY.")
    import hashlib

    from factorlab.security import workspace_root

    cache = workspace_root() / "prices"
    cache.mkdir(exist_ok=True)
    key = hashlib.sha256(f"{ticker}|{start}|{end}".encode()).hexdigest()
    path = cache / f"{key}.csv"
    meta_path = cache / f"{key}.json"
    if (
        not refresh
        and path.exists()
        and meta_path.exists()
        and time.time() - path.stat().st_mtime < cache_ttl
    ):
        close = pd.read_csv(path, index_col=0, parse_dates=True).iloc[:, 0].rename(ticker)
        close.attrs["provenance"] = {
            **json.loads(meta_path.read_text()),
            "cache_used": True,
            "ttl_seconds": cache_ttl,
        }
        return close
    frame = download_prices_with_retry(ticker, start, end)
    if frame.empty:
        raise ValueError(
            f"Sem preços para {ticker} após tentativas. Verifique rede, ticker e intervalo."
        )
    close = frame["Close"]
    if isinstance(close, pd.DataFrame):
        if close.shape[1] != 1:
            raise ValueError("A consulta deve conter apenas um ativo.")
        close = close.iloc[:, 0]
    close.index = pd.to_datetime(close.index).tz_localize(None)
    close = close.rename(ticker).astype(float)
    close.attrs["provenance"] = snapshot(
        close.to_csv().encode(), f"Yahoo Finance adjusted close: {ticker}"
    )
    path.write_text(close.to_csv(), encoding="utf-8")
    meta_path.write_text(json.dumps(close.attrs["provenance"]), encoding="utf-8")
    return close


def monthly_returns(prices: pd.Series, calendar: str = "NYSE") -> pd.Series:
    """Descarta mês corrente incompleto; não preenche preços/retornos ausentes."""
    prices = prices.sort_index().dropna()
    if prices.empty or (prices <= 0).any() or not np.isfinite(prices).all():
        raise ValueError("Preços devem ser positivos e finitos.")
    if prices.index.has_duplicates:
        raise ValueError("Datas duplicadas nos preços.")
    schedule = mcal.get_calendar(calendar).schedule(
        start_date=prices.index.min().to_period("M").start_time,
        end_date=prices.index.max().to_period("M").end_time,
    )
    expected = pd.Series(schedule.index, index=schedule.index).resample("ME").last()
    observed = pd.Series(prices.index, index=prices.index).resample("ME").last()
    monthly = prices.resample("ME").last().where(observed.eq(expected))
    current_month = pd.Timestamp.today().to_period("M").to_timestamp("M")
    monthly = monthly.loc[monthly.index < current_month]
    result = monthly.pct_change(fill_method=None).dropna().rename("asset_return")
    result.attrs["provenance"] = prices.attrs.get("provenance", {})
    return result


def read_returns_csv(source) -> pd.Series:
    """Contrato de entrada: date,return; retorno total mensal em USD e decimal."""
    frame = pd.read_csv(source)
    if frame.empty:
        raise ValueError("CSV não contém observações.")
    if not {"date", "return"}.issubset(frame.columns):
        raise ValueError("CSV deve conter as colunas date e return.")
    series = pd.Series(
        pd.to_numeric(frame["return"], errors="raise").to_numpy(),
        index=month_index(frame["date"]),
        name="asset_return",
    )
    if series.index.has_duplicates:
        raise ValueError("CSV contém meses duplicados.")
    if not np.isfinite(series).all() or (series < -1).any():
        raise ValueError("Retornos devem ser finitos, em decimal, e não inferiores a -1.")
    return series.sort_index()


def demo_data() -> tuple[pd.Series, pd.DataFrame]:
    """Amostra sintética reproduzível, nunca usada como fallback de dados reais."""
    rng = np.random.default_rng(42)
    dates = pd.date_range("2010-01-31", periods=180, freq="ME")
    factors = pd.DataFrame(
        rng.normal(
            [0.006, 0.001, 0.002, 0.002, 0.001], [0.04, 0.025, 0.025, 0.018, 0.018], (180, 5)
        ),
        index=dates,
        columns=["Mkt-RF", "SMB", "HML", "RMW", "CMA"],
    )
    factors["RF"] = 0.002
    factors["Mom"] = rng.normal(0.003, 0.03, len(dates))
    returns = (
        0.001
        + factors[["Mkt-RF", "SMB", "HML", "RMW", "CMA"]] @ np.array([1.1, 0.3, -0.2, 0.15, 0.1])
        + factors["RF"]
        + rng.normal(0, 0.015, len(dates))
    )
    return returns.rename("asset_return"), factors
