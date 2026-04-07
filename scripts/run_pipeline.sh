#!/usr/bin/env bash
set -euo pipefail

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
CYAN='\033[0;36m'
BOLD='\033[1m'
RESET='\033[0m'

STAGE="all"

usage() {
  echo ""
  echo "  ${BOLD}Lumina Pipeline Runner${RESET}"
  echo ""
  echo "  Usage: $0 [--stage <stage>]"
  echo ""
  echo "  Stages:"
  echo "    all        Run full pipeline (default)"
  echo "    ingest     Rust ingestion only"
  echo "    nlp        Python NLP (sentiment + topics + geopolitical)"
  echo "    train      Train regime classifier"
  echo "    predict    Run prediction on latest data"
  echo ""
}

while [[ $# -gt 0 ]]; do
  case $1 in
    --stage) STAGE="$2"; shift 2 ;;
    -h|--help) usage; exit 0 ;;
    *) echo "Unknown arg: $1"; usage; exit 1 ;;
  esac
done

log_start() {
  echo ""
  echo -e "${CYAN}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${RESET}"
  echo -e "${BOLD}  ▶ $1${RESET}"
  echo -e "${CYAN}  $(date '+%Y-%m-%d %H:%M:%S')${RESET}"
  echo -e "${CYAN}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${RESET}"
}

log_ok() {
  echo -e "${GREEN}  ✓ $1${RESET}"
}

log_warn() {
  echo -e "${YELLOW}  ⚠ $1${RESET}"
}

log_err() {
  echo -e "${RED}  ✗ $1${RESET}"
}

run_ingest() {
  log_start "Ingestion (Rust)"
  local t0=$SECONDS
  if docker compose run --rm ingestion all; then
    log_ok "Ingestion complete ($(( SECONDS - t0 ))s)"
  else
    log_warn "Ingestion returned non-zero — check source connectivity"
  fi
}

run_sentiment() {
  log_start "FinBERT sentiment scoring"
  local t0=$SECONDS
  docker compose run --rm pipeline sentiment
  log_ok "Sentiment complete ($(( SECONDS - t0 ))s)"
}

run_topics() {
  log_start "BERTopic topic modeling"
  local t0=$SECONDS
  docker compose run --rm pipeline topics
  log_ok "Topics complete ($(( SECONDS - t0 ))s)"
}

run_geopolitical() {
  log_start "GDELT geopolitical features"
  local t0=$SECONDS
  docker compose run --rm pipeline geopolitical
  log_ok "Geopolitical features complete ($(( SECONDS - t0 ))s)"
}

run_train() {
  log_start "Regime classifier training (XGBoost + MLflow)"
  local t0=$SECONDS
  docker compose run --rm pipeline train
  log_ok "Training complete ($(( SECONDS - t0 ))s)"
}

run_predict() {
  log_start "Latest regime prediction"
  local t0=$SECONDS
  docker compose run --rm pipeline predict
  log_ok "Prediction complete ($(( SECONDS - t0 ))s)"
}

run_nlp() {
  run_sentiment
  run_topics
  run_geopolitical
}

echo ""
echo -e "${BOLD}  Lumina · Alternative Data Signal Research${RESET}"
echo -e "  Stage: ${YELLOW}${STAGE}${RESET}"
echo ""

TOTAL_START=$SECONDS

case $STAGE in
  all)
    run_ingest
    run_nlp
    run_train
    run_predict
    ;;
  ingest)   run_ingest ;;
  nlp)      run_nlp ;;
  train)    run_train ;;
  predict)  run_predict ;;
  *)
    log_err "Unknown stage: $STAGE"
    usage
    exit 1
    ;;
esac

echo ""
echo -e "${GREEN}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${RESET}"
echo -e "${GREEN}${BOLD}  Pipeline complete — $(( SECONDS - TOTAL_START ))s total${RESET}"
echo -e "${GREEN}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${RESET}"
echo ""
