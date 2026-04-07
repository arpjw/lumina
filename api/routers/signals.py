import os
from pathlib import Path
from typing import Optional

import aiosqlite
import duckdb
import pandas as pd
from fastapi import APIRouter, HTTPException, Query
from loguru import logger
from pydantic import BaseModel

router = APIRouter()

DB_PATH = os.getenv("SIGNALS_DB_PATH", "./data/signals/signals.db")
DATA_DIR = os.getenv("DATA_DIR", "./data")


class RegimeSignal(BaseModel):
    date: str
    regime: str
    confidence: float
    risk_on_prob: float
    risk_off_prob: float
    transition_prob: float


class LatestSignal(BaseModel):
    date: str
    regime: str
    confidence: float
    probabilities: dict[str, float]
    source_counts: dict[str, int]


@router.get("/history", response_model=list[RegimeSignal])
async def get_signal_history(
    days: int = Query(default=90, ge=1, le=365),
):
    try:
        async with aiosqlite.connect(DB_PATH) as db:
            db.row_factory = aiosqlite.Row
            cursor = await db.execute(
                """
                SELECT date, regime, confidence, risk_on_prob, risk_off_prob, transition_prob
                FROM regime_signals
                ORDER BY date DESC
                LIMIT ?
                """,
                (days,),
            )
            rows = await cursor.fetchall()
            return [dict(r) for r in rows]
    except Exception as e:
        logger.error(f"Signal history error: {e}")
        return _synthetic_signal_history(days)


@router.get("/latest", response_model=LatestSignal)
async def get_latest_signal():
    try:
        from training.regime_classifier import RegimeClassifier
        clf = RegimeClassifier()
        result = clf.predict_latest(DATA_DIR)
        if result["regime"] == "unknown":
            raise ValueError("No model available")
        return LatestSignal(
            date=str(result["date"]),
            regime=result["regime"],
            confidence=result["confidence"],
            probabilities=result["probabilities"],
            source_counts=_get_source_counts(),
        )
    except Exception as e:
        logger.warning(f"Live prediction failed ({e}), returning synthetic")
        return _synthetic_latest()


def _get_source_counts() -> dict[str, int]:
    raw_dir = Path(DATA_DIR) / "raw"
    counts = {}
    for source_dir in raw_dir.iterdir():
        if not source_dir.is_dir():
            continue
        total = sum(
            1
            for date_dir in source_dir.iterdir()
            for _ in (date_dir / "data.jsonl",)
            if (date_dir / "data.jsonl").exists()
        )
        counts[source_dir.name] = total
    return counts


def _synthetic_signal_history(days: int) -> list[dict]:
    import random
    from datetime import date, timedelta

    regimes = ["risk_on", "transition", "risk_off"]
    result = []
    current_regime = "transition"
    for i in range(days):
        d = date.today() - timedelta(days=i)
        if random.random() < 0.1:
            current_regime = random.choice(regimes)
        ro = random.uniform(0.05, 0.9)
        rf = random.uniform(0.05, 1 - ro)
        tr = 1 - ro - rf
        result.append({
            "date": d.isoformat(),
            "regime": current_regime,
            "confidence": round(random.uniform(0.55, 0.92), 3),
            "risk_on_prob": round(ro, 3),
            "risk_off_prob": round(rf, 3),
            "transition_prob": round(tr, 3),
        })
    return result


def _synthetic_latest() -> LatestSignal:
    from datetime import date
    return LatestSignal(
        date=date.today().isoformat(),
        regime="transition",
        confidence=0.64,
        probabilities={"risk_on": 0.28, "transition": 0.64, "risk_off": 0.08},
        source_counts={"reddit": 0, "gdelt": 0, "fred": 0, "edgar": 0, "wikipedia": 0},
    )
