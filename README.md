# Lumina: Cross-Source Alternative Data Fusion for Systematic Macro Regime Detection

**Arya Somu**, Monolith Systematic LLC | 
[arya@monolithsystematic.com](mailto:arya@monolithsystematic.com)

SSRN: Abstract ID **6534258**

---

## Abstract

Systematic macro strategies have traditionally relied on price-derived signals -- trend momentum, carry, and volatility regimes inferred from futures markets. Lumina is an open-source research platform that constructs a complementary signal layer from four heterogeneous alternative data sources: Reddit financial communities, the GDELT global news event stream, FRED macroeconomic indicators, and Kalshi prediction market probabilities on Fed policy, CPI, GDP, and recession contracts. A multi-layer NLP and market-microstructure pipeline extracts daily FinBERT composite sentiment, a GDELT CAMEO-derived geopolitical conflict/cooperation scalar, live FRED macro series, and an open-interest-weighted Kalshi regime scalar computed from directionally-signed prediction market mid prices. Features are fused via an XGBoost classifier trained on VIX-indexed regime labels into a ternary macro regime output: `risk_on`, `transition`, `risk_off`. The full pipeline is served through a FastAPI backend with WebSocket live streaming and a Next.js research dashboard featuring interactive backtesting and SHAP-based model attribution.

---

## 1. Motivation

The proliferation of unstructured text data across financial news and social media, combined with the emergence of liquid event-contract prediction markets, has created an information set that quantitative macro practitioners have been slow to systematically exploit. Lumina provides a reproducible, end-to-end reference implementation that demonstrates how four structurally distinct free-tier data sources can be ingested, scored, and fused into a regime classifier with full provenance tracking.

---

## 2. Data Sources

| Source | Content | Ingestion | Volume / backfill |
|---|---|---|---|
| Reddit | r/investing, r/MacroEconomics, r/wallstreetbets, r/Economics | Arctic Shift historical dump + PRAW OAuth (live) | COVID crash, 2022-23 rate hike cycle, SVB collapse, post-SVB |
| GDELT 2.0 | Global news events with CAMEO codes and Goldstein scale | REST (no key) | 500-2000 events/day |
| FRED | 9 macro indicator series (UNRATE, CPIAUCSL, DGS10, DGS2, T10YIE, VIXCLS, DTWEXBGS, BAMLH0A0HYM2, MORTGAGE30US) | FRED API (free key) | 9 daily observations |
| Kalshi | 72 macro markets across KXFED, KXCPI, KXFEDDECISION, KXRATECUTCOUNT, KXGDP, KXUNEMP, KXINFL, KXRECESSION event series | Signed REST (RSA-PSS custom headers) | ~$13M total open interest across 6 near-term events |

Reddit ingestion uses the Arctic Shift historical archive to backfill four regime-relevant windows -- the COVID crash, the 2022-23 Fed rate hike cycle, the SVB collapse, and the post-SVB recovery -- before switching to PRAW for incremental daily updates. The Rust ingestion binary (`lumina-ingestion`) handles GDELT and FRED in parallel with Tokio, SHA-256 dedup, and Parquet sinks partitioned by source/date.

---

## 3. Signal Extraction Pipeline

### 3.1 Sentiment Layer (FinBERT)

Each ingested Reddit or GDELT text record is scored using `ProsusAI/finbert`, a BERT model fine-tuned on financial phrasebank data. The composite sentiment score is:

```
composite_t = P(positive) - P(negative)
```

Records are batched at 32 sequences with truncation at 512 tokens. Daily cross-source sentiment is the mean composite across all sources, bounded to [-1, 1].

### 3.2 Geopolitical Layer (GDELT CAMEO)

GDELT encodes news events using the CAMEO taxonomy, which classifies inter-actor events on a cooperation/conflict spectrum via the Goldstein scale in [-10, 10]. The daily geopolitical risk scalar is:

```
geo_risk_t = -0.6 * mean(Goldstein_t) / 10 + 0.4 * conflict_ratio_t
```

where `conflict_ratio_t` is the proportion of daily events with CAMEO codes 10-20 (hostile actions).

### 3.3 Macro Layer (FRED)

Nine core FRED series are pulled daily: UNRATE, CPIAUCSL, DGS10, DGS2, T10YIE, VIXCLS, DTWEXBGS, BAMLH0A0HYM2, MORTGAGE30US. VIXCLS also serves as the regime label source; the remaining eight feed the feature matrix directly.

### 3.4 Kalshi Prediction Market Layer

Kalshi's `/events/{event_ticker}` endpoint is called directly for six near-term macro events (`KXFED-26APR`, `KXFED-26JUN`, `KXCPI-26APR`, `KXCPI-26MAY`, `KXFEDDECISION-26APR`, `KXRATECUTCOUNT-26DEC31`) rather than using the `series_ticker` query, which returns illiquid far-dated 2027 contracts. Authentication uses three custom RSA-PSS signed headers (`KALSHI-ACCESS-KEY`, `KALSHI-ACCESS-SIGNATURE`, `KALSHI-ACCESS-TIMESTAMP`) -- not JWT. Prices are read from the `_dollars` suffix fields (`yes_bid_dollars`, `yes_ask_dollars`, `last_price_dollars`, `open_interest_fp`).

Each market is assigned a directional weight based on its event series and ticker threshold, converting YES probability into a risk-on (+) or risk-off (-) contribution:

| Bucket | Weight logic |
|---|---|
| KXRECESSION | -1.0 |
| KXFEDDECISION | -0.8 if hike, +0.6 if cut, +0.3 hold |
| KXFED target-rate threshold | -0.7 if T ≥ 4.25%, +0.7 otherwise |
| KXRATECUTCOUNT | +0.6 (more cuts = risk_on) |
| KXCPI / KXINFL | -0.6 above, +0.4 below |
| KXGDP | +0.5 above, -0.5 below |
| KXUNEMP | -0.4 above, +0.3 below |

The daily `kalshi_regime_scalar` is the open-interest-weighted mean of `(prob - 0.5) * 2 * weight` across all loaded markets, bounded to [-1, 1]. Zero-OI markets get a floor weight of 1.0 so thin markets still contribute.

---

## 4. Regime Classification

### 4.1 Label Construction

```
risk_on     : VIX < 15
transition  : 15 <= VIX <= 25
risk_off    : VIX > 25
```

VIX (FRED: VIXCLS) is chosen because it is a canonical systematic macro regime indicator, daily, free, and behaviorally unambiguous across the three buckets.

### 4.2 Feature Matrix

The feature matrix concatenates the sentiment, geopolitical, Kalshi, and FRED layers into a daily panel. All parquet parts are loaded through a unified `DatetimeIndex` join. As of April 10, 2026, the model trains on **16 features** after the Kalshi layer (`kalshi_regime_scalar`, `kalshi_n_markets`, `kalshi_n_weighted_markets`, `kalshi_total_open_interest`) is added to the fused panel.

### 4.3 XGBoost Classifier

```
n_estimators     = 200
max_depth        = 4
learning_rate    = 0.05
subsample        = 0.8
colsample_bytree = 0.8
eval_metric      = mlogloss
```

TimeSeriesSplit cross-validation (preserving temporal order) is used for all folds. All experiments are tracked in MLflow with per-fold accuracy, feature importance, and model artifacts logged automatically.

---

## 5. Current Signal (April 10, 2026)

| Metric | Value |
|---|---|
| Regime | **risk_off** |
| Confidence | 99.1% |
| Kalshi regime scalar | **-0.212** |
| Kalshi markets loaded | 72 |
| Kalshi total open interest | ~$13.1M |
| Feature count | 16 |
| CV accuracy | 98.7% |

The negative Kalshi scalar is consistent with elevated Fed-funds threshold probabilities and low rate-cut-count YES prices in the near-term event contracts -- the prediction market layer agrees with the text-derived signal that the current regime remains tightening-biased.

---

## 6. System Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│  Data Sources                                                   │
│  Reddit · GDELT · FRED · Kalshi                                 │
└──────────────────────────┬──────────────────────────────────────┘
                           │ Rust async ingestion (Tokio)
                           │ + Arctic Shift historical backfill
                           │ + Kalshi RSA-PSS signed REST client
                           ▼
┌─────────────────────────────────────────────────────────────────┐
│  Feature Store                                                  │
│  Parquet (partitioned by source/date) · DuckDB query layer      │
└──────────────────────────┬──────────────────────────────────────┘
                           │
            ┌──────────┬───┴────┬──────────┐
            ▼          ▼        ▼          ▼
         FinBERT    GDELT     FRED      Kalshi
         sentiment  CAMEO     macro     scalar
            │          │        │          │
            └──────────┴────┬───┴──────────┘
                            │ Feature matrix (16-dim)
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
| Kalshi client | Python, cryptography (RSA-PSS), requests |
| Feature store | Apache Parquet, DuckDB |
| NLP/ML | Python 3.11, FinBERT, XGBoost, scikit-learn, SHAP |
| Experiment tracking | MLflow 2.11 |
| Signal store | SQLite via aiosqlite |
| API | FastAPI 0.111, WebSockets, uvicorn |
| Frontend | Next.js 14, React 18, Recharts, TailwindCSS |
| Infrastructure | Docker Compose, launchd (daily cron) |

---

## 7. Running Locally

### 7.1 Environment

```bash
cp .env.example .env
```

Required variables:

```
FRED_API_KEY=...
REDDIT_CLIENT_ID=...
REDDIT_CLIENT_SECRET=...
REDDIT_USER_AGENT=lumina-research/0.1
KALSHI_API_KEY=<kalshi key id>
KALSHI_PRIVATE_KEY_PATH=/absolute/path/to/kalshi_private_key.pem
DATA_DIR=./data
```

### 7.2 Ingestion (Rust)

```bash
cd ingestion && cargo build --release
./target/release/ingest fred
./target/release/ingest gdelt
```

Reddit historical backfill:

```bash
cd pipeline
python backfill/run_backfill.py fetch --period covid_crash
python backfill/run_backfill.py fetch --period rate_hike_cycle
python backfill/run_backfill.py fetch --period svb_collapse
python backfill/run_backfill.py fetch --period post_svb
```

### 7.3 Pipeline (Python)

```bash
python pipeline/run_pipeline.py sentiment       # FinBERT composite
python pipeline/run_pipeline.py geopolitical    # GDELT CAMEO scalar
python pipeline/run_pipeline.py kalshi          # Kalshi prediction market layer
python pipeline/run_pipeline.py train           # XGBoost + MLflow
python pipeline/run_pipeline.py predict         # latest regime prediction
python pipeline/run_pipeline.py shap            # SHAP feature importance
```

### 7.4 API + Frontend

```bash
# API (requires DATA_DIR, KALSHI_API_KEY, KALSHI_PRIVATE_KEY_PATH in env)
cd api && python -m uvicorn main:app --reload --port 8000

# Frontend (second terminal)
cd frontend && npm install && npm run dev
```

- Dashboard  →  http://localhost:3000
- API docs   →  http://localhost:8000/docs
- Kalshi signal → `GET /kalshi/signal`, raw markets → `GET /kalshi/markets`
- MLflow UI  →  http://localhost:5001 (`docker compose up mlflow`)

### 7.5 Automated Daily Run

`scripts/daily_run.sh` is registered with launchd to fire at 06:00 local time every morning. It sources the API venv, exports the required env vars (including `KALSHI_API_KEY` and `KALSHI_PRIVATE_KEY_PATH`), runs FRED + GDELT ingestion, a Reddit backfill sweep for the `post_svb` window, then the full `sentiment → geopolitical → kalshi → train → predict` pipeline. MLflow tracks each run against the local SQLite registry at `models/registry/mlflow.db`.

To install the launchd job:

```bash
launchctl load ~/Library/LaunchAgents/com.lumina.daily.plist
```

---

## 8. Limitations and Future Work

**Label quality.** VIX-based regime labeling conflates volatility with risk regime. Alternative label construction from realized drawdown windows or HMM latent states is an obvious extension.

**Kalshi contract lifecycle.** The `MACRO_EVENTS` tuple is hardcoded to specific near-term event tickers. As events resolve, the list must be rolled forward manually. An automatic event-discovery layer that walks the series index and selects the nearest open event per series is planned.

**Cross-source weighting.** Sentiment aggregation currently weights Reddit and GDELT equally. A learned weighting scheme trained against downstream regime accuracy would likely improve signal quality.

**Signal decay.** No half-life or autocorrelation analysis has been performed. Text-derived regime signals may decay rapidly in efficient markets -- a critical empirical question before live deployment.

**Scope.** Current target is macro regime classification only. Asset-level sentiment, cross-sectional overlays, and earnings-surprise prediction are natural extensions.

---

## 9. Repository Structure

```
lumina/
├── ingestion/             # Rust binary: async multi-source fetch, dedup, Parquet sink
│   └── src/sources/       # reddit.rs · gdelt.rs · fred.rs
├── pipeline/              # Python NLP engine, Kalshi client, classifier
│   ├── nlp/               # sentiment.py · geopolitical.py
│   ├── signals/           # kalshi_features.py (RSA-PSS signed REST, regime scalar)
│   ├── backfill/          # Arctic Shift historical Reddit loader
│   └── training/          # regime_classifier.py (XGBoost + MLflow + SHAP)
├── api/                   # FastAPI backend
│   └── routers/           # signals · sentiment · geopolitical · kalshi · backtest · live
├── frontend/              # Next.js 14 research dashboard
│   └── src/components/    # dashboard · notebook · inspector · validation
├── scripts/               # daily_run.sh (launchd cron) · run_pipeline.sh
├── docker/                # Per-service Dockerfiles
└── docker-compose.yml     # Full stack: ingestion · pipeline · api · frontend · mlflow
```

---

## Citation

```
Somu, Arya. "Lumina: Cross-Source Alternative Data Fusion for Systematic
Macro Regime Detection." Monolith Systematic LLC, 2026.
SSRN Abstract ID: 6534258
https://github.com/arpjw/lumina
```

---

*Monolith Systematic LLC — Arya Somu*
