from __future__ import annotations

import os
from pathlib import Path
from typing import Optional

import pandas as pd
from bertopic import BERTopic
from loguru import logger
from sentence_transformers import SentenceTransformer


MACRO_TOPIC_LABELS = {
    "inflation": ["inflation", "cpi", "prices", "cost", "purchasing power"],
    "monetary_policy": ["federal reserve", "fed", "interest rate", "rate hike", "powell", "fomc"],
    "recession": ["recession", "gdp", "growth", "contraction", "slowdown"],
    "credit": ["credit", "yield", "spread", "default", "bond", "debt"],
    "geopolitics": ["war", "sanction", "geopolitical", "conflict", "china", "russia"],
    "labor": ["unemployment", "jobs", "payroll", "hiring", "layoffs"],
    "energy": ["oil", "energy", "gas", "crude", "opec"],
    "equity": ["stock", "market", "equities", "earnings", "valuation"],
}


class TopicEngine:
    def __init__(self, min_topic_size: Optional[int] = None):
        self.min_topic_size = min_topic_size or int(os.getenv("BERTOPIC_MIN_TOPIC_SIZE", "10"))
        self.embedding_model = SentenceTransformer("all-MiniLM-L6-v2")
        self.topic_model: Optional[BERTopic] = None

    def fit(self, texts: list[str]) -> BERTopic:
        logger.info(f"Fitting BERTopic on {len(texts)} documents (min_topic_size={self.min_topic_size})")
        self.topic_model = BERTopic(
            embedding_model=self.embedding_model,
            min_topic_size=self.min_topic_size,
            nr_topics="auto",
            calculate_probabilities=True,
            verbose=False,
        )
        self.topic_model.fit(texts)
        logger.info(f"BERTopic found {len(self.topic_model.get_topics())} topics")
        return self.topic_model

    def transform(self, texts: list[str]) -> tuple[list[int], list[float]]:
        if self.topic_model is None:
            raise RuntimeError("Model not fitted. Call fit() first.")
        topics, probs = self.topic_model.transform(texts)
        return topics, [float(p.max()) if hasattr(p, "max") else float(p) for p in probs]

    def label_macro_topics(self) -> dict[int, str]:
        if self.topic_model is None:
            return {}

        topic_info = self.topic_model.get_topics()
        labels = {}

        for topic_id, words in topic_info.items():
            if topic_id == -1:
                labels[topic_id] = "noise"
                continue
            word_list = [w for w, _ in words]
            word_str = " ".join(word_list).lower()
            best_label = "other"
            best_count = 0
            for label, keywords in MACRO_TOPIC_LABELS.items():
                count = sum(1 for kw in keywords if kw in word_str)
                if count > best_count:
                    best_count = count
                    best_label = label
            labels[topic_id] = best_label

        return labels

    def process_raw_data(self, data_dir: str) -> pd.DataFrame:
        raw_dir = Path(data_dir) / "raw"
        all_texts = []
        all_meta = []

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
                    texts = df["body"].fillna("").astype(str).tolist()
                    all_texts.extend(texts)
                    all_meta.extend(df[["id", "source", "source_type", "date"]].to_dict("records"))
                except Exception as e:
                    logger.warning(f"Failed to load {jsonl_path}: {e}")

        if not all_texts:
            logger.warning("No texts found for topic modeling")
            return pd.DataFrame()

        all_texts = [t[:512] for t in all_texts if len(t.strip()) > 20]
        self.fit(all_texts)
        topics, probs = self.transform(all_texts)
        macro_labels = self.label_macro_topics()

        result = pd.DataFrame(all_meta)
        result["topic_id"] = topics
        result["topic_prob"] = probs
        result["macro_label"] = result["topic_id"].map(macro_labels).fillna("other")

        out_path = Path(data_dir) / "features" / "topics"
        out_path.mkdir(parents=True, exist_ok=True)
        result.to_parquet(out_path / "topic_assignments.parquet", index=False)

        daily_topic = result.groupby(["date", "macro_label"]).size().unstack(fill_value=0).reset_index()
        daily_topic.to_parquet(out_path / "daily_topic_counts.parquet", index=False)

        logger.info(f"Topic modeling complete. {len(result)} documents, saved to {out_path}")
        return result


if __name__ == "__main__":
    data_dir = os.getenv("DATA_DIR", "./data")
    engine = TopicEngine()
    engine.process_raw_data(data_dir)
