"""Compute Spearman IC, IR, and hit rate for regime signals vs forward returns."""

import numpy as np
import pandas as pd
from scipy.stats import spearmanr
from loguru import logger

HORIZONS = [1, 5, 10]

# Signal mapping: risk_on_prob for risk-on assets, -risk_off_prob for safe-haven / USD
SIGNAL_MAP: dict[str, tuple[str, float]] = {
    "SPY":      ("risk_on_prob",  1.0),
    "GLD":      ("risk_on_prob",  1.0),
    "TLT":      ("risk_off_prob", -1.0),
    "DX-Y.NYB": ("risk_off_prob", -1.0),
}

ROLLING_WINDOW = 63  # ~1 quarter


def compute_ic_metrics(aligned_df: pd.DataFrame) -> pd.DataFrame:
    """Return a summary DataFrame with IC, p-value, IR, and hit rate per ticker × horizon."""
    records: list[dict] = []

    for ticker, (signal_col, sign) in SIGNAL_MAP.items():
        sub = aligned_df[aligned_df["ticker"] == ticker].copy()
        if sub.empty or signal_col not in sub.columns:
            continue

        sub = sub.sort_values("date").reset_index(drop=True)
        signal = sub[signal_col].astype(float) * sign

        for h in HORIZONS:
            ret_col = f"fwd_{h}d"
            mask = signal.notna() & sub[ret_col].notna()
            s = signal[mask].values
            r = sub.loc[mask, ret_col].values

            if len(s) < 30:
                continue

            # full-sample Spearman IC
            ic, ic_p = spearmanr(s, r)

            # rolling 63-day IC for IR calculation
            rolling_ics: list[float] = []
            for i in range(ROLLING_WINDOW, len(s)):
                window_s = s[i - ROLLING_WINDOW : i]
                window_r = r[i - ROLLING_WINDOW : i]
                rho, _ = spearmanr(window_s, window_r)
                if not np.isnan(rho):
                    rolling_ics.append(rho)

            mean_ic = np.mean(rolling_ics) if rolling_ics else ic
            std_ic = np.std(rolling_ics, ddof=1) if len(rolling_ics) > 1 else np.nan
            ir = (mean_ic / std_ic * np.sqrt(252)) if std_ic and std_ic > 0 else np.nan

            # hit rate: fraction where signal and return have same sign
            same_sign = np.sign(s) == np.sign(r)
            hit_rate = float(same_sign.mean())

            records.append({
                "ticker": ticker,
                "horizon": h,
                "ic": round(float(ic), 4),
                "ic_pvalue": round(float(ic_p), 4),
                "ir": round(float(ir), 4) if not np.isnan(ir) else None,
                "hit_rate": round(hit_rate, 4),
                "n_obs": int(mask.sum()),
            })

    result = pd.DataFrame(records)
    logger.info(f"Computed IC metrics for {len(result)} ticker×horizon combos")
    return result


def compute_rolling_ic(aligned_df: pd.DataFrame) -> pd.DataFrame:
    """Return a time-series of rolling 63-day Spearman IC per ticker (horizon=1d)."""
    rows: list[dict] = []

    for ticker, (signal_col, sign) in SIGNAL_MAP.items():
        sub = aligned_df[aligned_df["ticker"] == ticker].copy()
        if sub.empty or signal_col not in sub.columns:
            continue

        sub = sub.sort_values("date").reset_index(drop=True)
        signal = (sub[signal_col].astype(float) * sign).values
        ret = sub["fwd_1d"].values
        dates = sub["date"].values

        for i in range(ROLLING_WINDOW, len(signal)):
            ws = signal[i - ROLLING_WINDOW : i]
            wr = ret[i - ROLLING_WINDOW : i]
            mask = ~(np.isnan(ws) | np.isnan(wr))
            if mask.sum() < 20:
                continue
            rho, _ = spearmanr(ws[mask], wr[mask])
            if not np.isnan(rho):
                rows.append({"date": str(dates[i])[:10], "ticker": ticker, "rolling_ic": round(rho, 4)})

    return pd.DataFrame(rows)
