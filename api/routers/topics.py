import os
from pathlib import Path

import duckdb
from fastapi import APIRouter, Query
from loguru import logger

DATA_DIR = os.getenv("DATA_DIR", "./data")
router = APIRouter()


@router.get("/daily")
async def get_daily_topics(days: int = Query(default=30, ge=1, le=365)):
    path = Path(DATA_DIR) / "features" / "topics" / "daily_topic_counts.parquet"
    if not path.exists():
        return _synthetic_topics(days)
    try:
        con = duckdb.connect()
        df = con.execute(
            f"SELECT * FROM read_parquet('{path}') ORDER BY date DESC LIMIT {days}"
        ).df()
        return df.to_dict("records")
    except Exception as e:
        logger.error(f"Topics query failed: {e}")
        return _synthetic_topics(days)


@router.get("/summary")
async def get_topic_summary():
    path = Path(DATA_DIR) / "features" / "topics" / "daily_topic_counts.parquet"
    if not path.exists():
        return _synthetic_summary()
    try:
        con = duckdb.connect()
        df = con.execute(f"SELECT * FROM read_parquet('{path}')").df()
        numeric = df.drop(columns=["date"], errors="ignore").select_dtypes("number")
        summary = numeric.sum().sort_values(ascending=False).head(8)
        return {"dominant_topics": summary.to_dict()}
    except Exception as e:
        logger.error(f"Topic summary failed: {e}")
        return _synthetic_summary()


def _synthetic_topics(days: int):
    import random
    from datetime import date, timedelta
    topics = ["inflation", "monetary_policy", "recession", "credit", "geopolitics", "labor", "energy", "equity"]
    result = []
    for i in range(days):
        d = (date.today() - timedelta(days=i)).isoformat()
        row = {"date": d}
        for t in topics:
            row[t] = random.randint(0, 40)
        result.append(row)
    return result


def _synthetic_summary():
    return {
        "dominant_topics": {
            "monetary_policy": 342,
            "inflation": 289,
            "equity": 201,
            "geopolitics": 178,
            "recession": 134,
            "credit": 98,
            "labor": 87,
            "energy": 62,
        }
    }
