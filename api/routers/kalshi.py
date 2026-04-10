import json
import os
from pathlib import Path

import duckdb
from fastapi import APIRouter, Query
from loguru import logger

DATA_DIR = os.getenv("DATA_DIR", "./data")
router = APIRouter()


@router.get("/signal")
async def get_kalshi_signal(days: int = Query(default=60, ge=1, le=365)):
    """Return the daily Kalshi regime scalar time series."""
    path = Path(DATA_DIR) / "features" / "kalshi" / "daily_kalshi.parquet"
    if not path.exists():
        return []
    try:
        con = duckdb.connect()
        df = con.execute(
            f"SELECT date, kalshi_regime_scalar, kalshi_n_markets, "
            f"kalshi_n_weighted_markets, kalshi_total_open_interest "
            f"FROM read_parquet('{path}') ORDER BY date DESC LIMIT {days}"
        ).df()
        df["date"] = df["date"].astype(str)
        return df.to_dict("records")
    except Exception as e:
        logger.error(f"Kalshi signal query failed: {e}")
        return []


@router.get("/markets")
async def get_kalshi_markets():
    """Return the latest day's raw Kalshi market records."""
    raw_dir = Path(DATA_DIR) / "raw" / "kalshi"
    if not raw_dir.exists():
        return []
    dated = sorted([p for p in raw_dir.iterdir() if p.is_dir()], reverse=True)
    if not dated:
        return []
    latest = dated[0] / "data.jsonl"
    if not latest.exists():
        return []
    records = []
    try:
        with latest.open() as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    records.append(json.loads(line))
                except json.JSONDecodeError:
                    continue
    except Exception as e:
        logger.error(f"Failed to read Kalshi raw records: {e}")
        return []
    return {"date": dated[0].name, "count": len(records), "markets": records}
