#!/bin/zsh
source /Users/aryasomu/Lumina/api/.venv/bin/activate
source /Users/aryasomu/.cargo/env

export DATA_DIR=/Users/aryasomu/Lumina/data
export MLFLOW_TRACKING_URI=sqlite:////Users/aryasomu/Lumina/models/registry/mlflow.db
export PYTHONPATH=/Users/aryasomu/Lumina/pipeline
export FRED_API_KEY=$(grep FRED_API_KEY /Users/aryasomu/Lumina/.env | cut -d= -f2)
export KALSHI_API_KEY=$(grep "^KALSHI_API_KEY=" /Users/aryasomu/Lumina/.env | cut -d= -f2)
export KALSHI_PRIVATE_KEY_PATH=/Users/aryasomu/Lumina/kalshi_private_key.pem
export RUST_LOG=info

cd /Users/aryasomu/Lumina

echo "=== Lumina daily run $(date) ===" 

./ingestion/target/release/ingest fred
./ingestion/target/release/ingest gdelt

cd pipeline
PYTHONPATH=/Users/aryasomu/Lumina/pipeline python backfill/run_backfill.py fetch --period post_svb
cd ..

source api/.venv/bin/activate
python pipeline/run_pipeline.py sentiment
python pipeline/run_pipeline.py geopolitical
python pipeline/run_pipeline.py kalshi
python pipeline/run_pipeline.py train
python pipeline/run_pipeline.py predict

echo "=== Done $(date) ==="
