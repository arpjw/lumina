import os
from pathlib import Path

import duckdb
from fastapi import APIRouter, Query
from loguru import logger
from pydantic import BaseModel

DATA_DIR = os.getenv("DATA_DIR", "./data")
router = APIRouter()


class GeopoliticalDay(BaseModel):
    date: str
    mean_goldstein: float
    geopolitical_risk_score: float
    conflict_ratio: float
    total_events: int


@router.get("/daily", response_model=list[GeopoliticalDay])
async def get_daily_geopolitical(days: int = Query(default=60, ge=1, le=365)):
    path = Path(DATA_DIR) / "features" / "geopolitical" / "daily_geopolitical.parquet"
    if not path.exists():
        return _synthetic_geo(days)
    try:
        con = duckdb.connect()
        df = con.execute(
            f"SELECT date, mean_goldstein, geopolitical_risk_score, conflict_ratio, total_events "
            f"FROM read_parquet('{path}') ORDER BY date DESC LIMIT {days}"
        ).df()
        return df.to_dict("records")
    except Exception as e:
        logger.error(f"Geopolitical query failed: {e}")
        return _synthetic_geo(days)


def _synthetic_geo(days: int):
    import random
    from datetime import date, timedelta
    result = []
    risk = 0.3
    for i in range(days):
        d = (date.today() - timedelta(days=i)).isoformat()
        risk = max(-1, min(1, risk + random.gauss(0, 0.04)))
        goldstein = -risk * 6 + random.gauss(0, 0.5)
        result.append({
            "date": d,
            "mean_goldstein": round(goldstein, 4),
            "geopolitical_risk_score": round(risk, 4),
            "conflict_ratio": round(max(0, 0.3 + risk * 0.4 + random.gauss(0, 0.05)), 4),
            "total_events": random.randint(40, 300),
        })
    return result
