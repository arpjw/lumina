from __future__ import annotations

import os
from pathlib import Path

import pandas as pd
from loguru import logger

CAMEO_COOPERATION = {
    "01": 1.0, "02": 0.8, "03": 0.9, "04": 1.0, "05": 0.7,
    "06": 0.8, "07": 0.6, "08": 0.9,
}

CAMEO_CONFLICT = {
    "10": -0.3, "11": -0.5, "12": -0.7, "13": -0.6, "14": -0.9,
    "15": -1.0, "16": -0.8, "17": -0.9, "18": -0.7, "19": -0.6,
    "20": -1.0,
}


def goldstein_to_scalar(value: float) -> float:
    return value / 10.0


def cameo_to_conflict_cooperation(cameo_code: str) -> float:
    if not cameo_code or len(cameo_code) < 2:
        return 0.0
    prefix = cameo_code[:2]
    if prefix in CAMEO_CONFLICT:
        return CAMEO_CONFLICT[prefix]
    if prefix in CAMEO_COOPERATION:
        return CAMEO_COOPERATION[prefix]
    first = cameo_code[0]
    if first in ["1"]:
        return -0.3
    if first in ["0"]:
        return 0.4
    return 0.0


def process_gdelt_features(data_dir: str) -> pd.DataFrame:
    raw_dir = Path(data_dir) / "raw" / "gdelt"
    records = []

    for date_dir in sorted(raw_dir.iterdir()):
        jsonl_path = date_dir / "data.jsonl"
        if not jsonl_path.exists():
            continue
        try:
            df = pd.read_json(jsonl_path, lines=True)
            df["date"] = date_dir.name
            records.append(df)
        except Exception as e:
            logger.warning(f"GDELT feature load failed for {date_dir}: {e}")

    if not records:
        logger.warning("No GDELT records found for geopolitical feature extraction")
        return pd.DataFrame()

    df = pd.concat(records, ignore_index=True)

    def extract_goldstein(meta):
        if isinstance(meta, dict):
            return meta.get("goldstein_scale") or 0.0
        return 0.0

    def extract_tone(meta):
        if isinstance(meta, dict):
            return meta.get("tone") or 0.0
        return 0.0

    df["goldstein"] = df["metadata"].apply(extract_goldstein)
    df["tone"] = df["metadata"].apply(extract_tone)
    df["goldstein_scalar"] = df["goldstein"].apply(goldstein_to_scalar)
    df["tone_scalar"] = df["tone"] / 100.0

    daily = df.groupby("date").agg(
        mean_goldstein=("goldstein_scalar", "mean"),
        std_goldstein=("goldstein_scalar", "std"),
        mean_tone=("tone_scalar", "mean"),
        conflict_events=("goldstein_scalar", lambda x: (x < -0.3).sum()),
        cooperation_events=("goldstein_scalar", lambda x: (x > 0.3).sum()),
        total_events=("goldstein_scalar", "count"),
    ).reset_index()

    daily["conflict_ratio"] = daily["conflict_events"] / daily["total_events"].clip(lower=1)
    daily["geopolitical_risk_score"] = (
        -daily["mean_goldstein"] * 0.6 + daily["conflict_ratio"] * 0.4
    ).clip(-1, 1)

    out_path = Path(data_dir) / "features" / "geopolitical"
    out_path.mkdir(parents=True, exist_ok=True)
    daily.to_parquet(out_path / "daily_geopolitical.parquet", index=False)

    logger.info(f"Geopolitical features computed for {len(daily)} days")
    return daily


if __name__ == "__main__":
    data_dir = os.getenv("DATA_DIR", "./data")
    process_gdelt_features(data_dir)
