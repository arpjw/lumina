"""Fetch daily adjusted close for cross-asset tickers and compute forward returns."""

from pathlib import Path

import pandas as pd
import yfinance as yf
from loguru import logger

TICKERS = ["SPY", "TLT", "GLD", "DX-Y.NYB"]
HORIZONS = [1, 5, 10]
DATA_DIR = Path(__file__).resolve().parents[2] / "data"
OUTPUT_DIR = DATA_DIR / "features" / "validation"


def fetch_forward_returns(
    start: str = "2020-01-01",
    end: str | None = None,
) -> pd.DataFrame:
    """Download daily adjusted close and compute forward returns for each horizon."""
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    logger.info(f"Downloading adjusted close for {TICKERS}")
    raw = yf.download(TICKERS, start=start, end=end, auto_adjust=True)

    close = raw["Close"]
    if isinstance(close, pd.Series):
        close = close.to_frame()

    # Normalise column names — yfinance may return MultiIndex
    close.columns = [str(c).strip() for c in close.columns]

    frames: list[pd.DataFrame] = []
    for ticker in close.columns:
        series = close[ticker].dropna()
        tmp = pd.DataFrame({"date": series.index, "ticker": ticker, "close": series.values})
        for h in HORIZONS:
            tmp[f"fwd_{h}d"] = series.pct_change(h).shift(-h).values
        frames.append(tmp)

    df = pd.concat(frames, ignore_index=True)
    df["date"] = pd.to_datetime(df["date"]).dt.tz_localize(None)

    out_path = OUTPUT_DIR / "forward_returns.parquet"
    df.to_parquet(out_path, index=False)
    logger.info(f"Saved forward returns → {out_path} ({len(df)} rows)")
    return df


if __name__ == "__main__":
    fetch_forward_returns()
