"""Deduplicate backfill records against existing data/raw/reddit JSONL files."""

import json
from pathlib import Path

from loguru import logger

DATA_DIR = Path(__file__).resolve().parents[2] / "data"


def load_existing_ids(raw_dir: Path | None = None) -> set[str]:
    """Scan all existing reddit JSONL files and collect their IDs."""
    raw_dir = raw_dir or (DATA_DIR / "raw" / "reddit")
    ids: set[str] = set()

    if not raw_dir.exists():
        return ids

    for jsonl_path in raw_dir.rglob("data.jsonl"):
        with open(jsonl_path) as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    rec = json.loads(line)
                    ids.add(rec["id"])
                except (json.JSONDecodeError, KeyError):
                    continue

    logger.info(f"Loaded {len(ids)} existing record IDs from {raw_dir}")
    return ids


def dedup(records: list[dict], existing_ids: set[str] | None = None) -> list[dict]:
    """Remove records whose ID already exists, plus internal duplicates."""
    if existing_ids is None:
        existing_ids = load_existing_ids()

    seen: set[str] = set(existing_ids)
    unique: list[dict] = []

    for rec in records:
        rid = rec["id"]
        if rid not in seen:
            seen.add(rid)
            unique.append(rec)

    removed = len(records) - len(unique)
    logger.info(f"Dedup: {len(records)} → {len(unique)} records ({removed} duplicates removed)")
    return unique
