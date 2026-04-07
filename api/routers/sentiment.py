import os
from pathlib import Path

import duckdb
import pandas as pd
from fastapi import APIRouter, HTTPException, Query
from loguru import logger
from pydantic import BaseModel

DATA_DIR = os.getenv("DATA_DIR", "./data")

# ── Sentiment router ──────────────────────────────────────────────────────────
router = APIRouter()


class DailySentiment(BaseModel):
    date: str
    cross_composite: float
    cross_positive: float
    cross_negative: float
    cross_count: int


@router.get("/daily", response_model=list[DailySentiment])
async def get_daily_sentiment(days: int = Query(default=60, ge=1, le=365)):
    path = Path(DATA_DIR) / "features" / "sentiment" / "daily_aggregated.parquet"
    if not path.exists():
        return _synthetic_sentiment(days)
    try:
        con = duckdb.connect()
        df = con.execute(
            f"SELECT * FROM read_parquet('{path}') ORDER BY date DESC LIMIT {days}"
        ).df()
        return df.to_dict("records")
    except Exception as e:
        logger.error(f"Sentiment query failed: {e}")
        return _synthetic_sentiment(days)


def _synthetic_sentiment(days: int):
    import random
    from datetime import date, timedelta
    result = []
    for i in range(days):
        d = (date.today() - timedelta(days=i)).isoformat()
        base = random.gauss(0.05, 0.15)
        result.append({
            "date": d,
            "cross_composite": round(base, 4),
            "cross_positive": round(0.35 + base * 0.3, 4),
            "cross_negative": round(0.30 - base * 0.3, 4),
            "cross_count": random.randint(80, 400),
        })
    return result
