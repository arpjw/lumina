# Lumina: Cross-Source Alternative Data Fusion for Systematic Macro Regime Detection

**Arya Somu**
Monolith Systematic LLC | De Anza College
[arya@monolithsystematic.com](mailto:arya@monolithsystematic.com)

---

## Abstract

Systematic macro strategies have traditionally relied on price-derived signals -- trend momentum, carry, and volatility regimes inferred from futures markets. This work presents Lumina, an open-source research platform that constructs a complementary signal layer from five heterogeneous free alternative data sources: Reddit financial communities, the GDELT global news event stream, SEC EDGAR regulatory filings, FRED macroeconomic indicators, and the Wikimedia breaking-event stream. A three-layer NLP pipeline extracts daily sentiment scores (FinBERT), dominant macro topic distributions (BERTopic), and a geopolitical conflict/cooperation scalar (GDELT CAMEO event taxonomy). These signals are fused via an XGBoost classifier trained on VIX-indexed regime labels into a ternary macro regime output: `risk_on`, `transition`, `risk_off`. The fusion architecture follows a scalar-modulation design in which alternative data scores modulate regime probability continuously rather than acting as hard categorical overrides, preserving trend signal integrity while incorporating soft textual evidence. The full pipeline is served through a FastAPI backend with live WebSocket streaming and a Next.js research dashboard featuring interactive backtesting and SHAP-based model attribution.

---

## 1. Motivation

The proliferation of unstructured text data across financial news, regulatory filings, and social media has created an information asymmetry that quantitative practitioners have been slow to systematically exploit. While large institutions deploy proprietary NLP pipelines at scale, the academic and independent research communities lack accessible, end-to-end reference implementations that demonstrate how alternative data signals can be rigorously constructed, validated, and fused into actionable regime indicators.

Lumina addresses this gap with three specific contributions:

1. A reproducible ingestion and feature extraction pipeline across five structurally distinct free data sources, implemented in Rust for performance and Python for modeling flexibility.
2. A CAMEO-based geopolitical scalar that maps GDELT event taxonomy codes to a continuous conflict/cooperation dimension, providing a quantified geopolitical risk overlay without requiring paid data.
3. A scalar-modulation fusion architecture that treats alternative data as a probabilistic soft overlay on regime classification rather than a discrete signal, offering a principled alternative to voting ensembles or naive feature concatenation.

---

## 2. Data Sources

All five data sources are freely accessible with no subscription requirements.

| Source | Content | Ingestion method | Daily volume |
|---|---|---|---|
| Reddit | r/investing, r/MacroEconomics, r/wallstreetbets, r/Economics | PRAW OAuth (free) | 200-500 posts |
| GDELT 2.0 | Global news events with CAMEO codes and Goldstein scale | REST (no key) | 500-2000 events |
| SEC EDGAR | 8-K and 10-K filings, full-text search index | EDGAR API (no key) | 20-100 filings |
| FRED | 40 macro indicator series (UNRATE, CPI, DGS10, VIX, BAMLH0A0HYM2, ...) | FRED API (free key) | 40 observations |
| Wikipedia | Breaking event edits filtered by macro keywords | Wikimedia EventStream (no key) | 50-200 edits |

Ingestion is implemented as a Rust binary (`lumina-ingestion`) using Tokio for async concurrency, pulling all five sources in parallel with SHA-256 deduplication and JSONL/Parquet sinks partitioned by source and date.

---

## 3. Signal Extraction Pipeline

### 3.1 Sentiment Layer (FinBERT)

Each ingested text record is scored using `ProsusAI/finbert`, a BERT model fine-tuned on financial phrasebank data. The model outputs three class probabilities: positive, negative, neutral. A composite sentiment score is defined as:

```
composite_t = P(positive) - P(negative)
```

Records are batched at 32 sequences with truncation at 512 tokens. Daily cross-source sentiment is computed as the mean composite score across all sources, providing a single scalar in [-1, 1] per day.

### 3.2 Topic Layer (BERTopic)

Topic modeling is performed using BERTopic with `all-MiniLM-L6-v2` sentence embeddings. Topics are automatically discovered and subsequently mapped to eight macro-relevant categories via CAMEO keyword matching: `inflation`, `monetary_policy`, `recession`, `credit`, `geopolitics`, `labor`, `energy`, `equity`. Daily topic counts per category form an 8-dimensional feature vector capturing the dominant macro narrative at each point in time.

### 3.3 Geopolitical Layer (GDELT CAMEO)

GDELT encodes news events using the Conflict and Mediation Event Observations (CAMEO) taxonomy, which classifies inter-actor events on a cooperation/conflict spectrum. The Goldstein scale assigns each event a numeric score in [-10, 10]. A daily geopolitical risk scalar is computed as:

```
geo_risk_t = -0.6 * mean(Goldstein_t) / 10 + 0.4 * conflict_ratio_t
```

where `conflict_ratio_t` is the proportion of daily events with CAMEO codes indicating hostile action (codes 10-20). This scalar is bounded to [-1, 1] and inverted so that increasing geopolitical conflict maps to increasing risk.

---

## 4. Regime Classification

### 4.1 Label Construction

Ground truth regime labels are derived from the CBOE Volatility Index (FRED series: VIXCLS) using threshold-based segmentation:

```
risk_on     : VIX < 15
transition  : 15 <= VIX <= 25
risk_off    : VIX > 25
```

VIX is chosen as a label proxy because it is widely used in systematic macro as a regime indicator, is available at daily frequency from FRED at no cost, and has well-established behavioral interpretation across the three regimes.

### 4.2 Feature Matrix

The full feature matrix concatenates the sentiment layer (4 features), topic layer (8 features), geopolitical layer (5 features), and FRED macro indicators (up to 40 features) into a daily panel. Missing values arising from source outages or non-trading days are forward-filled and then zero-filled.

### 4.3 XGBoost Classifier

An XGBoost multi-class classifier is trained on the labeled panel using 3-fold TimeSeriesSplit cross-validation to preserve temporal ordering. Key hyperparameters:

```
n_estimators     = 200
max_depth        = 4
learning_rate    = 0.05
subsample        = 0.8
colsample_bytree = 0.8
eval_metric      = mlogloss
```

All experiments are tracked in MLflow with per-fold accuracy, feature importance, and model artifacts logged automatically.

### 4.4 Scalar Modulation Design

The architecture treats the XGBoost output as a continuous probability triplet rather than a hard classification. Downstream consumers receive `P(risk_on)`, `P(transition)`, `P(risk_off)` as a probability distribution, enabling them to modulate position sizing or risk parameters proportionally to regime confidence rather than applying binary regime switches. This design is motivated by the observation that macro regimes transition gradually -- discrete classification discards the gradient information encoded in the probability margins.

---

## 5. System Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│  Data Sources                                                   │
│  Reddit · GDELT · SEC EDGAR · FRED · Wikipedia                  │
└──────────────────────────┬──────────────────────────────────────┘
                           │ Rust async ingestion (Tokio)
                           ▼
┌─────────────────────────────────────────────────────────────────┐
│  Feature Store                                                  │
│  Parquet (partitioned by source/date) · DuckDB query layer      │
└──────────────────────────┬──────────────────────────────────────┘
                           │
              ┌────────────┼────────────┐
              ▼            ▼            ▼
         FinBERT       BERTopic     GDELT CAMEO
         sentiment     topics       geo scalar
              │            │            │
              └────────────┴────────────┘
                           │ Feature matrix
                           ▼
┌─────────────────────────────────────────────────────────────────┐
│  XGBoost Regime Classifier                                      │
│  MLflow tracking · SHAP attribution · TimeSeriesSplit CV        │
└──────────────────────────┬──────────────────────────────────────┘
                           │ P(risk_on, transition, risk_off)
                           ▼
┌─────────────────────────────────────────────────────────────────┐
│  FastAPI Backend                                                │
│  REST endpoints · WebSocket live stream · Backtest runner       │
└──────────────────────────┬──────────────────────────────────────┘
                           │
              ┌────────────┼────────────┐
              ▼            ▼            ▼
         Signal        Research      Model
         Dashboard     Notebook      Inspector
         (live gauge)  (backtest)    (SHAP · CM)
```

### Stack

| Layer | Technology |
|---|---|
| Ingestion | Rust 1.77, Tokio, reqwest, serde |
| Feature store | Apache Parquet, DuckDB |
| NLP/ML | Python 3.11, FinBERT, BERTopic, XGBoost, scikit-learn |
| Experiment tracking | MLflow 2.11 |
| Signal store | SQLite via aiosqlite |
| API | FastAPI 0.111, WebSockets, uvicorn |
| Frontend | Next.js 14, React 18, Recharts, TailwindCSS |
| Infrastructure | Docker Compose |

---

## 6. Research Dashboard

The platform ships with a three-view Next.js frontend served at `localhost:3000`.

**Signal Dashboard** -- Live macro regime gauge (WebSocket, 30s refresh), 60-day FinBERT sentiment time series, GDELT geopolitical risk chart, BERTopic dominant topic bars, and source activity grid.

**Research Notebook** -- Interactive signal explorer with configurable entry/exit thresholds, lookback window, and direction. Runs a vectorized backtest on any signal layer (sentiment, geopolitical, or composite) and returns a full tearsheet: equity curve, Sharpe, Sortino, Calmar, max drawdown, win rate, and trade count.

**Model Inspector** -- SHAP mean absolute value feature importance bar chart and 3x3 time-series cross-validated confusion matrix for the regime classifier, alongside the full model configuration table.

---

## 7. Quickstart

```bash
# Clone
git clone https://github.com/arpjw/lumina && cd lumina

# Configure (FRED API key + Reddit OAuth credentials)
cp .env.example .env && nano .env

# Start API (serves synthetic data immediately while pipeline runs)
cd api && python3 -m venv .venv && source .venv/bin/activate
pip install fastapi "uvicorn[standard]" websockets python-multipart \
  pydantic pydantic-settings sqlalchemy aiosqlite duckdb pandas \
  pyarrow numpy python-dotenv httpx xgboost scikit-learn loguru
python -m uvicorn main:app --reload --port 8000

# In a second terminal: start frontend
cd frontend && npm install && npm run dev

# Dashboard  →  http://localhost:3000
# API docs   →  http://localhost:8000/docs
# MLflow UI  →  http://localhost:5001 (requires docker compose up mlflow)
```

**Run the full pipeline** (after `.env` is configured):

```bash
./scripts/run_pipeline.sh                  # full run
./scripts/run_pipeline.sh --stage ingest   # ingestion only
./scripts/run_pipeline.sh --stage nlp      # NLP pipeline only
./scripts/run_pipeline.sh --stage train    # classifier training only
```

---

## 8. Limitations and Future Work

**Label quality.** VIX-based regime labeling is a practical proxy but conflates volatility with risk regime. Future work should explore alternative label construction using realized drawdown windows or HMM-derived latent states.

**Cross-source weighting.** The current sentiment aggregation weights all sources equally. A learned weighting scheme -- trained to maximize downstream regime prediction accuracy -- would likely improve signal quality, particularly given the noise characteristics of social media versus regulatory filings.

**Temporal alignment.** GDELT events and Reddit posts are timestamped at publication, not at the moment of market impact. A lag analysis to determine optimal signal-to-label alignment windows has not yet been conducted.

**Signal decay.** No analysis of signal half-life or autocorrelation has been performed. Systematic regime signals derived from text corpora may decay rapidly in efficient markets; this is a critical empirical question for live deployment.

**Scope.** The current implementation targets macro regime classification. Extension to asset-level sentiment signals, cross-sectional momentum overlays, or earnings surprise prediction are natural follow-on directions.

---

## 9. Repository Structure

```
lumina/
├── ingestion/          # Rust binary: async multi-source fetch, dedup, Parquet sink
│   └── src/sources/    # reddit.rs · gdelt.rs · edgar.rs · fred.rs · wikipedia.rs
├── pipeline/           # Python NLP engine and classifier
│   ├── nlp/            # sentiment.py · topics.py · geopolitical.py
│   └── training/       # regime_classifier.py (XGBoost + MLflow + SHAP)
├── api/                # FastAPI backend
│   └── routers/        # signals · sentiment · topics · geopolitical · backtest · live
├── frontend/           # Next.js 14 research dashboard
│   └── src/components/ # dashboard · notebook · inspector
├── docker/             # Per-service Dockerfiles
├── scripts/            # run_pipeline.sh orchestration
└── docker-compose.yml  # Full stack: ingestion · pipeline · api · frontend · mlflow
```

---

<<<<<<< HEAD
## Citation

If you reference this work, please cite as:

```
Somu, Arya. "Lumina: Cross-Source Alternative Data Fusion for Systematic
Macro Regime Detection." Polaris Research Group, De Anza College, 2026.
https://github.com/arpjw/lumina
```

---

*Affiliated: Monolith Systematic LLC*
=======
*Monolith Systematic LLC — Arya Somu*
>>>>>>> 3acb3efb2dcb33572f1367ffcdfbe636331322a6
