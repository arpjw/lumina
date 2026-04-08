"""Fetch historical Reddit posts from the Arctic Shift API."""

import hashlib
import json
import time
from datetime import datetime, timezone
from pathlib import Path

import requests
from loguru import logger

API_BASE = "https://arctic-shift.photon-reddit.com/api/posts/search"
PAGE_SIZE = 100
THROTTLE_SECONDS = 1.0

SUBREDDITS = ["investing", "MacroEconomics", "wallstreetbets", "Economics"]

PERIODS: dict[str, tuple[str, str]] = {
    "covid_crash":    ("2020-01-01", "2020-06-01"),
    "rate_hike_cycle": ("2022-01-01", "2022-12-31"),
    "svb_collapse":   ("2023-02-01", "2023-05-01"),
    "post_svb":       ("2023-05-01", "2024-01-01"),
}


def _make_id(post_id: str) -> str:
    """Deterministic ID matching existing ingestion: reddit_{sha256[:16]}."""
    digest = hashlib.sha256(f"reddit_{post_id}".encode()).hexdigest()[:16]
    return f"reddit_{digest}"


def _to_raw_record(post: dict) -> dict | None:
    """Convert an Arctic Shift post to the Lumina JSONL RawRecord schema."""
    selftext = (post.get("selftext") or "").strip()
    title = (post.get("title") or "").strip()

    # Skip deleted / removed / empty posts
    if selftext in ("[deleted]", "[removed]", ""):
        body = title
    else:
        body = f"{title}\n\n{selftext}"

    if len(body) < 20:
        return None

    created_utc = post.get("created_utc", 0)
    ts = datetime.fromtimestamp(created_utc, tz=timezone.utc).isoformat()
    subreddit = post.get("subreddit", "unknown")
    permalink = post.get("permalink", "")

    return {
        "id": _make_id(post["id"]),
        "source": f"reddit/r/{subreddit}",
        "source_type": "social",
        "timestamp": ts,
        "title": title or None,
        "body": body,
        "url": f"https://reddit.com{permalink}" if permalink else None,
        "metadata": {
            "score": post.get("score", 0),
            "num_comments": post.get("num_comments", 0),
            "upvote_ratio": post.get("upvote_ratio"),
            "subreddit": subreddit,
            "sort": "historical",
        },
    }


def fetch_period(
    subreddit: str,
    after: str,
    before: str,
    *,
    max_pages: int = 200,
) -> list[dict]:
    """Paginate through Arctic Shift for one subreddit × date range.

    Returns a list of Lumina RawRecord dicts.
    """
    records: list[dict] = []
    page_after: int | None = None

    for page in range(max_pages):
        params: dict = {
            "subreddit": subreddit,
            "after": after,
            "before": before,
            "limit": PAGE_SIZE,
            "sort": "created_utc",
            "order": "asc",
        }
        if page_after is not None:
            params["after"] = page_after

        resp = requests.get(API_BASE, params=params, timeout=30)
        resp.raise_for_status()
        data = resp.json().get("data", [])

        if not data:
            break

        for post in data:
            rec = _to_raw_record(post)
            if rec:
                records.append(rec)

        # Advance cursor: use last post's created_utc
        page_after = data[-1].get("created_utc", 0)

        logger.debug(
            f"  r/{subreddit} page {page + 1}: {len(data)} posts "
            f"({len(records)} kept so far)"
        )

        if len(data) < PAGE_SIZE:
            break

        time.sleep(THROTTLE_SECONDS)

    return records


def fetch_all(
    periods: dict[str, tuple[str, str]] | None = None,
    subreddits: list[str] | None = None,
) -> list[dict]:
    """Fetch all subreddits × periods. Returns flat list of RawRecord dicts."""
    periods = periods or PERIODS
    subreddits = subreddits or SUBREDDITS
    all_records: list[dict] = []

    for period_name, (after, before) in periods.items():
        logger.info(f"Period: {period_name} ({after} → {before})")
        for sub in subreddits:
            logger.info(f"  Fetching r/{sub}")
            recs = fetch_period(sub, after, before)
            logger.info(f"  r/{sub}: {len(recs)} records")
            all_records.extend(recs)

    logger.info(f"Total fetched: {len(all_records)} records across all periods")
    return all_records
