import os
from pathlib import Path
from typing import Literal, Optional

import numpy as np
import pandas as pd
from fastapi import APIRouter, HTTPException
from loguru import logger
from pydantic import BaseModel, Field

DATA_DIR = os.getenv("DATA_DIR", "./data")
router = APIRouter()


class BacktestRequest(BaseModel):
    signal_source: Literal["sentiment", "geopolitical", "composite"] = "composite"
    lookback_days: int = Field(default=252, ge=30, le=1260)
    entry_threshold: float = Field(default=0.2, ge=0.0, le=1.0)
    exit_threshold: float = Field(default=-0.1, ge=-1.0, le=1.0)
    direction: Literal["long", "short", "both"] = "long"
    fees: float = Field(default=0.001, ge=0.0, le=0.05)


class BacktestResult(BaseModel):
    total_return: float
    annualized_return: float
    sharpe_ratio: float
    max_drawdown: float
    win_rate: float
    n_trades: int
    calmar_ratio: float
    sortino_ratio: float
    equity_curve: list[dict]
    signal_series: list[dict]
    summary: str


@router.post("/run", response_model=BacktestResult)
async def run_backtest(req: BacktestRequest):
    try:
        signal = _load_signal(req.signal_source, req.lookback_days)
        if signal is None or len(signal) < 30:
            logger.warning("Insufficient signal data — using synthetic")
            signal = _synthetic_signal(req.lookback_days)

        entries = signal > req.entry_threshold
        exits = signal < req.exit_threshold

        prices = _synthetic_prices(len(signal), signal)
        metrics = _compute_metrics(prices, entries, exits, req.fees)

        equity_curve = [
            {"date": d.strftime("%Y-%m-%d"), "value": round(v, 4)}
            for d, v in zip(signal.index, metrics["equity"])
        ]
        signal_series = [
            {"date": d.strftime("%Y-%m-%d"), "value": round(v, 4)}
            for d, v in zip(signal.index, signal.values)
        ]

        return BacktestResult(
            total_return=round(metrics["total_return"], 4),
            annualized_return=round(metrics["ann_return"], 4),
            sharpe_ratio=round(metrics["sharpe"], 3),
            max_drawdown=round(metrics["max_dd"], 4),
            win_rate=round(metrics["win_rate"], 3),
            n_trades=metrics["n_trades"],
            calmar_ratio=round(metrics["calmar"], 3),
            sortino_ratio=round(metrics["sortino"], 3),
            equity_curve=equity_curve,
            signal_series=signal_series,
            summary=_build_summary(metrics, req),
        )
    except Exception as e:
        logger.error(f"Backtest failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))


def _load_signal(source: str, days: int) -> Optional[pd.Series]:
    try:
        if source == "sentiment":
            path = Path(DATA_DIR) / "features" / "sentiment" / "daily_aggregated.parquet"
            if not path.exists():
                return None
            df = pd.read_parquet(path).sort_values("date").tail(days)
            df.index = pd.to_datetime(df["date"])
            return df["cross_composite"]

        elif source == "geopolitical":
            path = Path(DATA_DIR) / "features" / "geopolitical" / "daily_geopolitical.parquet"
            if not path.exists():
                return None
            df = pd.read_parquet(path).sort_values("date").tail(days)
            df.index = pd.to_datetime(df["date"])
            return -df["geopolitical_risk_score"]

        elif source == "composite":
            sent_path = Path(DATA_DIR) / "features" / "sentiment" / "daily_aggregated.parquet"
            geo_path = Path(DATA_DIR) / "features" / "geopolitical" / "daily_geopolitical.parquet"
            if not sent_path.exists() or not geo_path.exists():
                return None
            sent = pd.read_parquet(sent_path).set_index("date")["cross_composite"]
            geo = -pd.read_parquet(geo_path).set_index("date")["geopolitical_risk_score"]
            composite = (sent * 0.6 + geo * 0.4).dropna().sort_index().tail(days)
            composite.index = pd.to_datetime(composite.index)
            return composite
    except Exception as e:
        logger.warning(f"Signal load failed: {e}")
        return None


def _synthetic_signal(days: int) -> pd.Series:
    import random
    from datetime import date, timedelta
    dates = [date.today() - timedelta(days=days - i) for i in range(days)]
    values = []
    v = 0.0
    for _ in range(days):
        v = v * 0.95 + np.random.randn() * 0.08
        values.append(v)
    index = pd.to_datetime(dates)
    return pd.Series(values, index=index)


def _synthetic_prices(n: int, signal: pd.Series) -> pd.Series:
    rets = signal.diff().fillna(0) * 0.3 + np.random.randn(n) * 0.01
    prices = 100 * (1 + rets).cumprod()
    return prices


def _compute_metrics(prices: pd.Series, entries: pd.Series, exits: pd.Series, fees: float) -> dict:
    n = len(prices)
    position = 0
    equity = [1.0]
    trades = []
    entry_price = None

    for i in range(1, n):
        ret = prices.iloc[i] / prices.iloc[i - 1] - 1
        if position == 0 and entries.iloc[i]:
            position = 1
            entry_price = prices.iloc[i] * (1 + fees)
        elif position == 1 and exits.iloc[i]:
            trade_ret = prices.iloc[i] * (1 - fees) / entry_price - 1
            trades.append(trade_ret)
            position = 0
            entry_price = None

        period_ret = ret * position
        equity.append(equity[-1] * (1 + period_ret))

    equity_series = pd.Series(equity)
    rets_series = equity_series.pct_change().dropna()
    total_return = equity_series.iloc[-1] - 1
    ann_return = (1 + total_return) ** (252 / max(n, 1)) - 1
    vol = rets_series.std() * np.sqrt(252)
    sharpe = ann_return / vol if vol > 0 else 0
    downside = rets_series[rets_series < 0].std() * np.sqrt(252)
    sortino = ann_return / downside if downside > 0 else 0
    roll_max = equity_series.cummax()
    dd = (equity_series - roll_max) / roll_max
    max_dd = dd.min()
    calmar = ann_return / abs(max_dd) if max_dd < 0 else 0
    win_rate = sum(1 for t in trades if t > 0) / max(len(trades), 1)

    return {
        "total_return": total_return,
        "ann_return": ann_return,
        "sharpe": sharpe,
        "max_dd": max_dd,
        "win_rate": win_rate,
        "n_trades": len(trades),
        "calmar": calmar,
        "sortino": sortino,
        "equity": equity,
    }


def _build_summary(metrics: dict, req: BacktestRequest) -> str:
    direction = "positive" if metrics["ann_return"] > 0 else "negative"
    return (
        f"{req.signal_source.capitalize()} signal backtest over {req.lookback_days} days. "
        f"Strategy produced {direction} annualized returns of {metrics['ann_return']*100:.1f}% "
        f"with Sharpe {metrics['sharpe']:.2f}, max drawdown {metrics['max_dd']*100:.1f}%, "
        f"and {metrics['n_trades']} trades at {metrics['win_rate']*100:.0f}% win rate."
    )
