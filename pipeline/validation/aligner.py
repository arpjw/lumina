"""Load regime signals from SQLite and align them with forward-return dates."""

import sqlite3
from pathlib import Path

import pandas as pd
from loguru import logger

DATA_DIR = Path(__file__).resolve().parents[2] / "data"
DB_PATH = DATA_DIR / "signals" / "signals.db"
RETURNS_PATH = DATA_DIR / "features" / "validation" / "forward_returns.parquet"


def align_signals_to_returns(
    returns_df: pd.DataFrame | None = None,
) -> pd.DataFrame:
    """Forward-fill regime signals onto the market-calendar dates in the returns frame."""

    if returns_df is None:
        returns_df = pd.read_parquet(RETURNS_PATH)

    # --- load regime signals from SQLite ---
    con = sqlite3.connect(str(DB_PATH))
    signals = pd.read_sql(
        "SELECT date, regime, risk_on_prob, risk_off_prob, transition_prob FROM regime_signals ORDER BY date",
        con,
    )
    con.close()

    if signals.empty:
        logger.warning("No regime signals found in DB — returning empty frame")
        for col in ["regime", "risk_on_prob", "risk_off_prob", "transition_prob"]:
            returns_df[col] = None
        return returns_df

    signals["date"] = pd.to_datetime(signals["date"])

    # build a daily index spanning the returns dates, forward-fill signals
    all_dates = pd.DataFrame({"date": returns_df["date"].drop_duplicates().sort_values()})
    signals = all_dates.merge(signals, on="date", how="left")
    signals = signals.ffill()

    merged = returns_df.merge(signals, on="date", how="left")
    logger.info(f"Aligned {len(merged)} rows ({merged['regime'].notna().sum()} with signal)")
    return merged


if __name__ == "__main__":
    df = align_signals_to_returns()
    print(df.head(10))
