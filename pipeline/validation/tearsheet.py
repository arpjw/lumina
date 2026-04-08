"""Orchestrator: fetch → align → compute IC metrics → save tearsheet."""

from pathlib import Path

from loguru import logger

from pipeline.validation.fetcher import fetch_forward_returns
from pipeline.validation.aligner import align_signals_to_returns
from pipeline.validation.metrics import compute_ic_metrics, compute_rolling_ic

OUTPUT_DIR = Path(__file__).resolve().parents[2] / "data" / "features" / "validation"


def run_validation(start: str = "2020-01-01") -> dict:
    """Run the full validation pipeline and return result dict."""
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    logger.info("Step 1/3: Fetching forward returns")
    returns_df = fetch_forward_returns(start=start)

    logger.info("Step 2/3: Aligning regime signals")
    aligned = align_signals_to_returns(returns_df)

    logger.info("Step 3/3: Computing IC metrics")
    summary = compute_ic_metrics(aligned)
    rolling = compute_rolling_ic(aligned)

    out_path = OUTPUT_DIR / "ic_tearsheet.parquet"
    summary.to_parquet(out_path, index=False)
    logger.info(f"Saved IC tearsheet → {out_path}")

    return {
        "summary": summary.to_dict(orient="records"),
        "rolling_ic": rolling.to_dict(orient="records"),
    }


if __name__ == "__main__":
    result = run_validation()
    import json
    print(json.dumps(result["summary"], indent=2))
