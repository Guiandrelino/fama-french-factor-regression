"""Execução sem dashboard e exportação de resultados."""

import argparse
import json
from pathlib import Path

from factorlab.data import demo_data, load_factors, load_prices, monthly_returns, read_returns_csv
from factorlab.regression import fit_model


def main():
    parser = argparse.ArgumentParser(description="FactorLab — regressão mensal Fama–French")
    source = parser.add_mutually_exclusive_group(required=True)
    source.add_argument("--ticker", help="Ativo americano, por exemplo SPY")
    source.add_argument("--csv", help="CSV com date,return (USD, decimal)")
    source.add_argument("--demo", action="store_true", help="Dados sintéticos offline")
    parser.add_argument("--model", choices=["CAPM", "FF3", "FF5", "CARHART4", "FF6"], default="FF5")
    parser.add_argument("--start", default="2015-01-01")
    parser.add_argument("--end", default=None, help="Data final exclusiva")
    parser.add_argument("--hac-lags", type=int, default=3)
    parser.add_argument("--window", type=int, default=36)
    parser.add_argument("--refresh", action="store_true")
    parser.add_argument("--output", default="outputs")
    args = parser.parse_args()
    try:
        if args.demo:
            returns, factors = demo_data()
        else:
            returns = (
                read_returns_csv(args.csv)
                if args.csv
                else monthly_returns(load_prices(args.ticker, args.start, args.end))
            )
            factors = load_factors(args.model, refresh=args.refresh)
            returns = returns.loc[args.start : args.end]
        result = fit_model(returns, factors, args.model, args.hac_lags, args.window)
    except Exception as exc:
        parser.exit(1, f"Erro: {exc}\n")
    output = Path(args.output)
    output.mkdir(parents=True, exist_ok=True)
    result.coefficients.to_csv(output / "coefficients.csv")
    result.data.join(result.fitted).join(result.residuals).to_csv(output / "observations.csv")
    result.rolling.to_csv(output / "rolling.csv")
    report = {
        "model": args.model,
        "source": "synthetic" if args.demo else args.csv or args.ticker,
        "start": str(result.data.index.min().date()),
        "end": str(result.data.index.max().date()),
        "metrics": result.metrics,
        "diagnostics": result.diagnostics,
    }
    (output / "report.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(json.dumps(report, indent=2))
    print(f"\nArquivos exportados para {output.resolve()}")


if __name__ == "__main__":
    main()
