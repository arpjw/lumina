from __future__ import annotations

import base64
import datetime as dt
import json
import os
import re
from pathlib import Path
from typing import Any, Optional
from urllib.parse import urlencode

import pandas as pd
import requests
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import padding
from loguru import logger

BASE_URL = "https://api.elections.kalshi.com/trade-api/v2"

# Specific near-term macro event tickers. Fetched individually via
# /events/{event_ticker}. The series query endpoint returns far-dated
# 2027+ contracts with no liquidity; addressing each event directly
# gives us the currently-trading markets we actually want.
MACRO_EVENTS = (
    "KXFED-26APR",            # April 29 2026 Fed meeting
    "KXFED-26JUN",            # June 2026 Fed meeting
    "KXCPI-26APR",            # April 2026 CPI
    "KXCPI-26MAY",            # May 2026 CPI
    "KXFEDDECISION-26APR",    # April Fed decision
    "KXRATECUTCOUNT-26DEC31", # 2026 rate cut count
)

# High-rate threshold (%). KXFED rate-level markets with T >= this are
# read as "rates remain elevated" = risk_off when YES resolves.
HIGH_RATE_THRESHOLD = 4.25

# Pulls a threshold letter + numeric value out of a ticker like
# "KXFED-25DEC-T4.25" or "KXCPI-25SEP-B3.1" → ("T", 4.25) / ("B", 3.1).
_THRESHOLD_RE = re.compile(r"-([TBUAH])(\d+(?:\.\d+)?)")

# Title keyword buckets for directional inference (used when the ticker
# doesn't encode a threshold letter).
_HIKE_WORDS = ("HIKE", "RAISE", "INCREASE", "ABOVE", "HIGHER")
_CUT_WORDS = ("CUT", "LOWER", "DECREASE", "BELOW", "UNDER")
_HOT_INFL_WORDS = ("ABOVE", "HIGHER", "HOT", "EXCEED", "OVER")
_COOL_INFL_WORDS = ("BELOW", "LOWER", "UNDER", "COOL")


def _load_private_key(path: str):
    with open(path, "rb") as f:
        return serialization.load_pem_private_key(f.read(), password=None)


def _sign_request(private_key, method: str, path: str) -> dict[str, str]:
    """Build the 3 Kalshi auth headers. `path` must NOT include query params."""
    key_id = os.getenv("KALSHI_API_KEY")
    if not key_id:
        raise RuntimeError("KALSHI_API_KEY not set")

    timestamp = str(int(dt.datetime.now().timestamp() * 1000))
    msg = (timestamp + method.upper() + path).encode()
    signature = private_key.sign(
        msg,
        padding.PSS(
            mgf=padding.MGF1(hashes.SHA256()),
            salt_length=padding.PSS.DIGEST_LENGTH,
        ),
        hashes.SHA256(),
    )
    return {
        "KALSHI-ACCESS-KEY": key_id,
        "KALSHI-ACCESS-SIGNATURE": base64.b64encode(signature).decode(),
        "KALSHI-ACCESS-TIMESTAMP": timestamp,
        "Accept": "application/json",
    }


def _kalshi_get(private_key, path: str, params: Optional[dict[str, Any]] = None) -> dict[str, Any]:
    """GET a Kalshi endpoint with signed headers. `path` is the API path
    without query params (e.g. '/markets' or '/events/KXFED-26APR'); the
    signature uses the full prefixed path ('/trade-api/v2' + path).
    Query params are NOT included in the signature."""
    sig_path = f"/trade-api/v2{path}"
    if params:
        url = f"{BASE_URL}{path}?{urlencode(params)}"
    else:
        url = f"{BASE_URL}{path}"
    headers = _sign_request(private_key, "GET", sig_path)
    resp = requests.get(url, headers=headers, timeout=30)
    resp.raise_for_status()
    return resp.json()


def fetch_markets() -> list[dict[str, Any]]:
    """Fetch macro markets by pulling each known near-term event directly.

    Calls `/events/{event_ticker}` once per entry in MACRO_EVENTS and
    returns every market contained in those events. Each market is tagged
    with the parent event ticker and a derived `_series` (the event ticker
    prefix) for downstream directional weighting. Per-event failures are
    logged and skipped.
    """
    key_path = os.getenv("KALSHI_PRIVATE_KEY_PATH")
    if not key_path or not Path(key_path).exists():
        raise RuntimeError(f"KALSHI_PRIVATE_KEY_PATH not set or file missing: {key_path}")

    private_key = _load_private_key(key_path)

    all_markets: list[dict[str, Any]] = []
    for event_ticker in MACRO_EVENTS:
        try:
            result = _kalshi_get(private_key, f"/events/{event_ticker}")
            markets = result.get("markets", []) or []
            series = event_ticker.split("-")[0]
            logger.info(f"Kalshi event={event_ticker} returned {len(markets)} markets")
            for m in markets:
                m["_series"] = series
                m["_event_ticker"] = event_ticker
                all_markets.append(m)
        except Exception as e:
            logger.warning(f"Kalshi fetch failed for event={event_ticker}: {e}")

    logger.info(f"Kalshi macro total: {len(all_markets)} markets across {len(MACRO_EVENTS)} events")
    return all_markets


def _parse_threshold(ticker: str) -> tuple[Optional[str], Optional[float]]:
    """Return (letter, value) from the first '-X<number>' segment, or (None, None)."""
    m = _THRESHOLD_RE.search(ticker.upper())
    if not m:
        return (None, None)
    try:
        return (m.group(1), float(m.group(2)))
    except ValueError:
        return (m.group(1), None)


def _any_in(haystack: str, needles: tuple[str, ...]) -> bool:
    return any(n in haystack for n in needles)


def _directional_weight(series: str, ticker: str, title: str) -> float:
    """Map a macro market to a directional weight for the regime scalar.

    Convention: YES probability reflects the likelihood of the outcome the
    contract describes. The weight converts that outcome into a risk-on (+)
    or risk-off (-) signal.
    """
    t = ticker.upper()
    tt = (title or "").upper()
    letter, value = _parse_threshold(t)

    # Recession contracts
    if series == "KXRECESSION" or "RECESSION" in t or "RECESSION" in tt:
        return -1.0

    # Rate-cut count (more cuts = easier policy = risk_on)
    if series == "KXRATECUTCOUNT":
        return +0.6

    # Fed decision outcome (hike / hold / cut)
    if series == "KXFEDDECISION":
        if letter == "H" or _any_in(tt, _HIKE_WORDS):
            return -0.8
        if _any_in(tt, _CUT_WORDS):
            return +0.6
        return +0.3  # hold / unknown = mild risk_on

    # Fed target-rate threshold markets
    if series == "KXFED":
        if value is not None:
            return -0.7 if value >= HIGH_RATE_THRESHOLD else +0.7
        # Fall back to title hints
        if _any_in(tt, _HIKE_WORDS):
            return -0.7
        if _any_in(tt, _CUT_WORDS):
            return +0.7
        return 0.0

    # Inflation
    if series in ("KXCPI", "KXINFL"):
        if letter in ("A", "T") or _any_in(tt, _HOT_INFL_WORDS):
            return -0.6
        if letter == "B" or _any_in(tt, _COOL_INFL_WORDS):
            return +0.4
        return -0.3

    # GDP
    if series == "KXGDP":
        if letter in ("A", "T") or _any_in(tt, ("ABOVE", "HIGHER", "EXCEED")):
            return +0.5
        if letter == "B" or _any_in(tt, ("BELOW", "LOWER", "UNDER")):
            return -0.5
        return 0.0

    # Unemployment
    if series == "KXUNEMP":
        if letter in ("A", "T") or _any_in(tt, ("ABOVE", "HIGHER", "RISE")):
            return -0.4
        if letter == "B" or _any_in(tt, ("BELOW", "LOWER", "FALL")):
            return +0.3
        return 0.0

    return 0.0


def _extract_record(m: dict[str, Any]) -> Optional[dict[str, Any]]:
    ticker = m.get("ticker", "") or ""
    title = m.get("title", "") or m.get("yes_sub_title", "") or ""
    series = m.get("_series") or ""
    event_ticker = m.get("_event_ticker") or ""

    def _f(key: str) -> float:
        try:
            return float(m.get(key) or 0)
        except (TypeError, ValueError):
            return 0.0

    # Kalshi now returns prices in dollars (0..1) via the *_dollars fields.
    yes_bid = _f("yes_bid_dollars")
    yes_ask = _f("yes_ask_dollars")
    last_price = _f("last_price_dollars")
    open_interest = _f("open_interest_fp")
    volume = _f("volume")

    if yes_bid or yes_ask:
        mid_price: Optional[float] = (yes_bid + yes_ask) / 2.0
    elif last_price:
        mid_price = last_price
    else:
        mid_price = None

    return {
        "ticker": ticker,
        "title": title,
        "series": series,
        "event_ticker": event_ticker,
        "yes_bid": yes_bid,
        "yes_ask": yes_ask,
        "last_price": last_price,
        "mid_price": mid_price,
        "open_interest": open_interest,
        "volume": volume,
        "directional_weight": _directional_weight(series, ticker, title),
    }


def compute_regime_scalar(records: list[dict[str, Any]]) -> float:
    """Open-interest-weighted directional signal in [-1, 1].

    Per-market signal = (prob - 0.5) * 2 * directional_weight, where prob
    is the YES mid price in dollars (already [0, 1]). Markets without a
    mid price carry no information and are skipped for the scalar, but
    they're still written to JSONL upstream.

    Weighting falls back to a floor of 1.0 so a day where every market
    has OI=0 still produces a meaningful average instead of collapsing.
    """
    num = 0.0
    den = 0.0
    for r in records:
        w = r.get("directional_weight") or 0.0
        if w == 0.0:
            continue
        mid = r.get("mid_price")
        if mid is None:
            continue
        prob = max(0.0, min(1.0, float(mid)))
        signal = (prob - 0.5) * 2.0 * w
        oi = r.get("open_interest") or 0
        weight = max(float(oi), 1.0)
        num += signal * weight
        den += weight
    if den == 0:
        return 0.0
    return max(-1.0, min(1.0, num / den))


def run(data_dir: str) -> dict[str, Any]:
    """Fetch Kalshi macro markets, write raw jsonl + daily feature parquet."""
    today = dt.date.today().isoformat()

    raw_dir = Path(data_dir) / "raw" / "kalshi" / today
    raw_dir.mkdir(parents=True, exist_ok=True)
    raw_path = raw_dir / "data.jsonl"

    features_dir = Path(data_dir) / "features" / "kalshi"
    features_dir.mkdir(parents=True, exist_ok=True)
    parquet_path = features_dir / "daily_kalshi.parquet"

    try:
        markets = fetch_markets()
    except Exception as e:
        logger.error(f"Kalshi fetch failed: {e}")
        return {"error": str(e), "n_markets": 0}

    records: list[dict[str, Any]] = []
    with raw_path.open("w") as f:
        for m in markets:
            rec = _extract_record(m)
            if rec is None:
                continue
            rec["fetched_at"] = dt.datetime.utcnow().isoformat()
            f.write(json.dumps(rec) + "\n")
            records.append(rec)

    logger.info(f"Kept {len(records)} Kalshi macro markets; wrote {raw_path}")

    scalar = compute_regime_scalar(records)

    weighted_oi = sum(float(r.get("open_interest") or 0) for r in records if r.get("directional_weight"))
    n_weighted = sum(1 for r in records if r.get("directional_weight"))

    row = {
        "date": pd.to_datetime(today),
        "kalshi_regime_scalar": float(scalar),
        "kalshi_n_markets": len(records),
        "kalshi_n_weighted_markets": int(n_weighted),
        "kalshi_total_open_interest": float(weighted_oi),
    }

    if parquet_path.exists():
        try:
            existing = pd.read_parquet(parquet_path)
            existing = existing[existing["date"] != row["date"]]
            df = pd.concat([existing, pd.DataFrame([row])], ignore_index=True)
        except Exception as e:
            logger.warning(f"Could not read existing kalshi parquet, overwriting: {e}")
            df = pd.DataFrame([row])
    else:
        df = pd.DataFrame([row])

    df = df.sort_values("date").reset_index(drop=True)
    df.to_parquet(parquet_path, index=False)

    logger.info(
        f"Kalshi regime scalar={scalar:.4f} over {n_weighted} weighted markets "
        f"(total OI {weighted_oi}); saved to {parquet_path}"
    )

    return {
        "n_markets": len(records),
        "n_weighted": n_weighted,
        "kalshi_regime_scalar": scalar,
        "raw_path": str(raw_path),
        "features_path": str(parquet_path),
    }


if __name__ == "__main__":
    from dotenv import load_dotenv
    load_dotenv()
    data_dir = os.getenv("DATA_DIR", "./data")
    print(run(data_dir))
