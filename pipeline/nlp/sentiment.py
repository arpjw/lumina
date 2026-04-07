from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

import duckdb
import pandas as pd
import torch
from loguru import logger
from transformers import AutoModelForSequenceClassification, AutoTokenizer


@dataclass
class SentimentScore:
    record_id: str
    source: str
    source_type: str
    date: str
    positive: float
    negative: float
    neutral: float
    composite: float
    text_length: int


class FinBERTEngine:
    MODEL_NAME = "ProsusAI/finbert"
    BATCH_SIZE = 32
    MAX_LENGTH = 512

    def __init__(self, model_name: Optional[str] = None):
        model_name = model_name or os.getenv("FINBERT_MODEL", self.MODEL_NAME)
        logger.info(f"Loading FinBERT from {model_name}")
        self.tokenizer = AutoTokenizer.from_pretrained(model_name)
        self.model = AutoModelForSequenceClassification.from_pretrained(model_name)
        self.device = "cuda" if torch.cuda.is_available() else "cpu"
        self.model.to(self.device)
        self.model.eval()
        logger.info(f"FinBERT loaded on {self.device}")

    def score_texts(self, texts: list[str]) -> list[dict]:
        results = []
        for i in range(0, len(texts), self.BATCH_SIZE):
            batch = texts[i : i + self.BATCH_SIZE]
            encoded = self.tokenizer(
                batch,
                padding=True,
                truncation=True,
                max_length=self.MAX_LENGTH,
                return_tensors="pt",
            ).to(self.device)

            with torch.no_grad():
                outputs = self.model(**encoded)
                probs = torch.softmax(outputs.logits, dim=-1).cpu().numpy()

            for prob in probs:
                # FinBERT label order: positive=0, negative=1, neutral=2
                results.append({
                    "positive": float(prob[0]),
                    "negative": float(prob[1]),
                    "neutral": float(prob[2]),
                    "composite": float(prob[0] - prob[1]),
                })

        return results

    def process_raw_data(self, data_dir: str, output_dir: str) -> pd.DataFrame:
        raw_dir = Path(data_dir) / "raw"
        all_records = []

        for source_dir in raw_dir.iterdir():
            if not source_dir.is_dir():
                continue
            for date_dir in sorted(source_dir.iterdir()):
                jsonl_path = date_dir / "data.jsonl"
                if not jsonl_path.exists():
                    continue
                try:
                    df = pd.read_json(jsonl_path, lines=True)
                    df["date"] = date_dir.name
                    all_records.append(df)
                except Exception as e:
                    logger.warning(f"Failed to load {jsonl_path}: {e}")

        if not all_records:
            logger.warning("No raw records found")
            return pd.DataFrame()

        df = pd.concat(all_records, ignore_index=True)
        df = df.dropna(subset=["body"])
        df["body"] = df["body"].astype(str).str.strip()
        df = df[df["body"].str.len() > 20]

        logger.info(f"Scoring {len(df)} records with FinBERT")
        texts = df["body"].tolist()
        scores = self.score_texts(texts)
        scores_df = pd.DataFrame(scores)

        result = pd.concat([df[["id", "source", "source_type", "date"]].reset_index(drop=True), scores_df], axis=1)
        result["text_length"] = df["body"].str.len().values

        out_path = Path(output_dir) / "features" / "sentiment"
        out_path.mkdir(parents=True, exist_ok=True)
        result.to_parquet(out_path / "sentiment_scores.parquet", index=False)
        logger.info(f"Saved sentiment scores to {out_path}")

        return result

    def aggregate_daily(self, scores_df: pd.DataFrame) -> pd.DataFrame:
        if scores_df.empty:
            return pd.DataFrame()

        agg = scores_df.groupby(["date", "source_type"]).agg(
            mean_composite=("composite", "mean"),
            mean_positive=("positive", "mean"),
            mean_negative=("negative", "mean"),
            std_composite=("composite", "std"),
            count=("composite", "count"),
            mean_text_length=("text_length", "mean"),
        ).reset_index()

        cross_source = scores_df.groupby("date").agg(
            cross_composite=("composite", "mean"),
            cross_positive=("positive", "mean"),
            cross_negative=("negative", "mean"),
            cross_count=("composite", "count"),
        ).reset_index()

        return cross_source


def run(data_dir: str, output_dir: str):
    engine = FinBERTEngine()
    scores = engine.process_raw_data(data_dir, output_dir)
    if not scores.empty:
        daily = engine.aggregate_daily(scores)
        out_path = Path(output_dir) / "features" / "sentiment" / "daily_aggregated.parquet"
        daily.to_parquet(out_path, index=False)
        logger.info(f"Daily sentiment aggregation complete: {len(daily)} days")
    return scores


if __name__ == "__main__":
    import sys
    data_dir = os.getenv("DATA_DIR", "./data")
    run(data_dir, data_dir)
