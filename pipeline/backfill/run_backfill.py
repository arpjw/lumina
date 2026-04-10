"""Orchestrate Reddit historical backfill: fetch → dedup → write JSONL."""

import json
from datetime import datetime
from pathlib import Path

from loguru import logger

from backfill.arctic_shift import fetch_all, PERIODS, SUBREDDITS
from backfill.dedup import dedup

DATA_DIR = Path(__file__).resolve().parents[2] / "data"


def _write_records(records: list[dict], output_dir: Path) -> int:
    """Write records into data/raw/reddit/{date}/data.jsonl grouped by date."""
    by_date: dict[str, list[dict]] = {}

    for rec in records:
        ts = rec.get("timestamp", "")
        date_str = ts[:10]  # YYYY-MM-DD from ISO timestamp
        if not date_str:
            continue
        by_date.setdefault(date_str, []).append(rec)

    total = 0
    for date_str, recs in sorted(by_date.items()):
        day_dir = output_dir / date_str
        day_dir.mkdir(parents=True, exist_ok=True)
        jsonl_path = day_dir / "data.jsonl"

        # Append to existing file if present
        mode = "a" if jsonl_path.exists() else "w"
        with open(jsonl_path, mode) as f:
            for rec in recs:
                f.write(json.dumps(rec, ensure_ascii=False) + "\n")

        total += len(recs)
        logger.debug(f"  {date_str}: {len(recs)} records")

    return total


def run_backfill(
    periods: dict[str, tuple[str, str]] | None = None,
    subreddits: list[str] | None = None,
) -> dict:
    """Run full backfill pipeline and return summary."""
    periods = periods or PERIODS
    subreddits = subreddits or SUBREDDITS
    output_dir = DATA_DIR / "raw" / "reddit"
    output_dir.mkdir(parents=True, exist_ok=True)

    logger.info("=== Reddit Historical Backfill (Arctic Shift) ===")
    logger.info(f"Periods: {list(periods.keys())}")
    logger.info(f"Subreddits: {subreddits}")

    # Step 1: Fetch
    raw_records = fetch_all(periods=periods, subreddits=subreddits)

    # Step 2: Dedup against existing data
    unique_records = dedup(raw_records)

    # Step 3: Write to disk
    n_written = _write_records(unique_records, output_dir)

    summary = {
        "fetched": len(raw_records),
        "after_dedup": len(unique_records),
        "written": n_written,
        "periods": list(periods.keys()),
        "subreddits": subreddits,
    }
    logger.info(f"Backfill complete: {summary}")
    return summary


if __name__ == "__main__":
    run_backfill()
