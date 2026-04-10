from __future__ import annotations

import os
from pathlib import Path
from typing import Optional

import mlflow
import mlflow.sklearn
import numpy as np
import pandas as pd
import shap
import xgboost as xgb
from loguru import logger
from sklearn.metrics import classification_report, confusion_matrix
from sklearn.model_selection import TimeSeriesSplit
from sklearn.preprocessing import LabelEncoder


REGIME_LABELS = ["risk_off", "transition", "risk_on"]


def load_feature_matrix(data_dir: str) -> pd.DataFrame:
    features_dir = Path(data_dir) / "features"

    parts = []

    sentiment_path = features_dir / "sentiment" / "daily_aggregated.parquet"
    if sentiment_path.exists():
        sent = pd.read_parquet(sentiment_path)
        parts.append(sent.set_index("date"))

    geo_path = features_dir / "geopolitical" / "daily_geopolitical.parquet"
    if geo_path.exists():
        geo = pd.read_parquet(geo_path)
        parts.append(geo.set_index("date"))

    topic_path = features_dir / "topics" / "daily_topic_counts.parquet"
    if topic_path.exists():
        topics = pd.read_parquet(topic_path)
        if "date" in topics.columns:
            topics = topics.set_index("date")
        parts.append(topics)

    if not parts:
        raise FileNotFoundError("No feature files found. Run the NLP pipeline first.")

    df = pd.concat(parts, axis=1, join="outer").fillna(0)
    df = df.sort_index()
    return df


def label_regimes_from_fred(data_dir: str, feature_df: pd.DataFrame) -> pd.Series:
    raw_dir = Path(data_dir) / "raw" / "fred"
    vix_values = {}

    for date_dir in sorted(raw_dir.iterdir()):
        jsonl_path = date_dir / "data.jsonl"
        if not jsonl_path.exists():
            continue
        try:
            df = pd.read_json(jsonl_path, lines=True)
            vix_rows = df[df["body"].str.contains("VIXCLS:", na=False)]
            for _, row in vix_rows.iterrows():
                try:
                    val = float(row["body"].split(":")[1].strip())
                    date = row["metadata"]["date"] if isinstance(row["metadata"], dict) else date_dir.name
                    vix_values[date] = val
                except Exception:
                    pass
        except Exception:
            pass

    if vix_values:
        vix_series = pd.Series(vix_values)
        vix_series.index = pd.to_datetime(vix_series.index)
        vix_daily = vix_series.resample("D").interpolate()
        aligned = vix_daily.reindex(pd.to_datetime(feature_df.index), method="nearest")
        labels = pd.cut(
            aligned,
            bins=[-np.inf, 15, 25, np.inf],
            labels=["risk_on", "transition", "risk_off"]
        ).astype(str)
        return labels

    logger.warning("No VIX data found — using synthetic regime labels")
    n = len(feature_df)
    synthetic = np.random.choice(REGIME_LABELS, size=n, p=[0.35, 0.3, 0.35])
    return pd.Series(synthetic, index=feature_df.index)


class RegimeClassifier:
    def __init__(self):
        self.model: Optional[xgb.XGBClassifier] = None
        self.label_encoder = LabelEncoder()
        self.feature_names: list[str] = []
        self.explainer: Optional[shap.TreeExplainer] = None

    def train(self, data_dir: str) -> dict:
        mlflow_uri = os.getenv("MLFLOW_TRACKING_URI", "http://localhost:5001")
        experiment = os.getenv("MLFLOW_EXPERIMENT_NAME", "lumina-regime-classifier")
        mlflow.set_tracking_uri(mlflow_uri)
        mlflow.set_experiment(experiment)

        X = load_feature_matrix(data_dir)
        y = label_regimes_from_fred(data_dir, X)

        valid_mask = y.notna()
        X = X[valid_mask]
        y = y[valid_mask]

        self.feature_names = X.columns.tolist()
        y_enc = self.label_encoder.fit_transform(y)

        params = {
            "n_estimators": 200,
            "max_depth": 4,
            "learning_rate": 0.05,
            "subsample": 0.8,
            "colsample_bytree": 0.8,
            "use_label_encoder": False,
            "eval_metric": "mlogloss",
            "random_state": 42,
        }

        tscv = TimeSeriesSplit(n_splits=2)
        fold_reports = []

        with mlflow.start_run(run_name="regime-classifier"):
            mlflow.log_params(params)
            mlflow.log_param("n_features", len(self.feature_names))
            mlflow.log_param("n_samples", len(X))
            mlflow.log_param("feature_names", str(self.feature_names[:10]))

            for fold, (train_idx, val_idx) in enumerate(tscv.split(X)):
                X_train, X_val = X.iloc[train_idx], X.iloc[val_idx]
                y_train, y_val = y_enc[train_idx], y_enc[val_idx]

                model = xgb.XGBClassifier(**params)
                model.fit(X_train, y_train, verbose=False)

                preds = model.predict(X_val)
                report = classification_report(y_val, preds, output_dict=True, zero_division=0)
                fold_reports.append(report)
                mlflow.log_metric(f"fold_{fold}_accuracy", report["accuracy"])

            self.model = xgb.XGBClassifier(**params)
            self.model.fit(X.values, y_enc)
            self.explainer = shap.TreeExplainer(self.model)

            mlflow.sklearn.log_model(self.model, "regime_classifier")

            out_path = Path(data_dir).parent / "models" / "regime_classifier"
            out_path.mkdir(parents=True, exist_ok=True)
            self.model.save_model(str(out_path / "model.json"))
            np.save(str(out_path / "label_classes.npy"), self.label_encoder.classes_)
            pd.Series(self.feature_names).to_csv(str(out_path / "feature_names.csv"), index=False)

            logger.info(f"Model trained and saved to {out_path}")

        mean_acc = np.mean([r["accuracy"] for r in fold_reports])
        return {"mean_cv_accuracy": mean_acc, "n_features": len(self.feature_names)}

    def predict_latest(self, data_dir: str) -> dict:
        X = load_feature_matrix(data_dir)
        if X.empty:
            return {"regime": "unknown", "probabilities": {}}

        model_path = Path(data_dir).parent / "models" / "regime_classifier" / "model.json"
        if not model_path.exists():
            logger.warning("No trained model found. Train first.")
            return {"regime": "unknown", "probabilities": {}}

        model = xgb.XGBClassifier()
        model.load_model(str(model_path))

        classes = np.load(str(model_path.parent / "label_classes.npy"), allow_pickle=True)
        feature_names = pd.read_csv(str(model_path.parent / "feature_names.csv"))["0"].tolist()

        X_aligned = X.reindex(columns=feature_names, fill_value=0)
        latest = X_aligned.iloc[[-1]]

        probs = model.predict_proba(latest)[0]
        pred_idx = probs.argmax()

        return {
            "regime": classes[pred_idx],
            "confidence": float(probs[pred_idx]),
            "probabilities": {cls: float(p) for cls, p in zip(classes, probs)},
            "date": X.index[-1],
        }

    def compute_shap(self, data_dir: str, n_samples: int = 50) -> pd.DataFrame:
        X = load_feature_matrix(data_dir)
        model_path = Path(data_dir).parent / "models" / "regime_classifier" / "model.json"
        model = xgb.XGBClassifier()
        model.load_model(str(model_path))

        feature_names = pd.read_csv(str(model_path.parent / "feature_names.csv"))["0"].tolist()
        X_aligned = X.reindex(columns=feature_names, fill_value=0).tail(n_samples)

        explainer = shap.TreeExplainer(model)
        shap_values = explainer.shap_values(X_aligned)

        if isinstance(shap_values, list):
            shap_mean = np.abs(np.array(shap_values)).mean(axis=0).mean(axis=0)
        else:
            shap_mean = np.abs(shap_values).mean(axis=0)

        importance_df = pd.DataFrame({
            "feature": feature_names,
            "mean_shap": shap_mean,
        }).sort_values("mean_shap", ascending=False)

        return importance_df


if __name__ == "__main__":
    data_dir = os.getenv("DATA_DIR", "./data")
    clf = RegimeClassifier()
    metrics = clf.train(data_dir)
    logger.info(f"Training complete: {metrics}")
    result = clf.predict_latest(data_dir)
    logger.info(f"Latest regime prediction: {result}")
