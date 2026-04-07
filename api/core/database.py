import os
from pathlib import Path

import aiosqlite
from loguru import logger

DB_PATH = os.getenv("SIGNALS_DB_PATH", "./data/signals/signals.db")


async def init_db():
    db_path = Path(DB_PATH)
    db_path.parent.mkdir(parents=True, exist_ok=True)

    async with aiosqlite.connect(str(db_path)) as db:
        await db.execute("""
            CREATE TABLE IF NOT EXISTS regime_signals (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                date TEXT NOT NULL UNIQUE,
                regime TEXT NOT NULL,
                confidence REAL,
                risk_on_prob REAL,
                risk_off_prob REAL,
                transition_prob REAL,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP
            )
        """)
        await db.execute("""
            CREATE TABLE IF NOT EXISTS pipeline_runs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                run_at TEXT DEFAULT CURRENT_TIMESTAMP,
                stage TEXT NOT NULL,
                status TEXT NOT NULL,
                records_processed INTEGER,
                duration_seconds REAL,
                notes TEXT
            )
        """)
        await db.commit()
    logger.info(f"Database ready at {db_path}")


async def get_db():
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        yield db
