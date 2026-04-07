# Lumina — Alternative Data Signal Research Platform

> Multi-source NLP signal engine for systematic macro regime detection.

Lumina ingests five free alternative data sources (Reddit, GDELT news, SEC EDGAR, FRED macro, Wikipedia events), runs a three-layer NLP/ML pipeline (FinBERT sentiment · BERTopic topic modeling · GDELT CAMEO geopolitical scoring), and fuses them into daily macro regime signals served through a live research dashboard.

Built as a standalone research platform. Zero paid APIs. Fully containerized.

---

## Architecture

```
Data Sources (5)  →  Rust Ingestion Pipeline  →  Parquet Feature Store
                                                         ↓
                       Python NLP Engine  →  XGBoost Regime Classifier
                                                         ↓
                              FastAPI Backend (REST + WebSocket)
                                                         ↓
               Next.js Dashboard  ·  Research Notebook  ·  Model Inspector
```

## Stack

| Layer | Tech |
|---|---|
| Ingestion | Rust (Tokio, reqwest, arrow2) |
| NLP/ML | Python, FinBERT, BERTopic, scikit-learn, XGBoost |
| Experiment tracking | MLflow |
| Feature store | DuckDB over Parquet |
| Signal store | SQLite |
| API | FastAPI, WebSockets, uvicorn |
| Frontend | Next.js 14, React, Recharts, TailwindCSS |
| Infra | Docker Compose |

## Quickstart

```bash
# 1. Clone and enter
git clone https://github.com/yourhandle/lumina && cd lumina

# 2. Copy env template
cp .env.example .env

# 3. Start everything
docker compose up --build

# 4. Open
#   Dashboard   → http://localhost:3000
#   API docs    → http://localhost:8000/docs
#   MLflow UI   → http://localhost:5001
```

## Data Sources (all free)

| Source | What we pull | API |
|---|---|---|
| Reddit | r/investing, r/MacroEconomics, r/wallstreetbets | PRAW (free) |
| GDELT | Global news event stream | GDELT 2.0 (free, no key) |
| SEC EDGAR | 8-K, 10-K, earnings filings | EDGAR full-text search (free) |
| FRED | 40+ macro indicators | FRED API (free key) |
| Wikipedia | Breaking event edits | Wikimedia EventStream (free) |

## Signal Pipeline

1. **Sentiment layer** — FinBERT scored per source per day → cross-source weighted composite
2. **Topic layer** — BERTopic identifies dominant macro themes (inflation, rates, geopolitics, credit)
3. **Geopolitical layer** — GDELT CAMEO event codes mapped to conflict/cooperation scalar
4. **Regime classifier** — XGBoost fuses all three into `{risk_on, risk_off, transition}` daily label

## Project Structure

```
lumina/
├── ingestion/          # Rust binary: fetch → normalize → Parquet
├── pipeline/           # Python: NLP, signals, backtest, training
├── api/                # FastAPI: REST + WebSocket endpoints
├── frontend/           # Next.js 14 dashboard
├── models/             # MLflow artifact store
├── data/               # raw/, features/, signals/
├── notebooks/          # Exploratory research notebooks
├── docker/             # Per-service Dockerfiles
└── docker-compose.yml
```

## Research Notes

Signal fusion architecture follows a scalar-modulation design: geopolitical and sentiment scores modulate regime probability rather than overriding it. This preserves trend signal integrity while incorporating alternative data as a soft overlay — analogous to the approach described in the Monolith Systematic geopolitical macro signal layer.

---

*Polaris Research Group / Monolith Systematic LLC — Arya Somu*
