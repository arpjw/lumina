import os
from contextlib import asynccontextmanager

from dotenv import load_dotenv
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from loguru import logger

from core.database import init_db
from routers import signals, sentiment, topics, geopolitical, backtest, live, validation

load_dotenv()


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("Lumina API starting up")
    await init_db()
    logger.info("Database initialized")
    yield
    logger.info("Lumina API shutting down")


app = FastAPI(
    title="Lumina API",
    description="Alternative data signal research platform for systematic macro regime detection",
    version="0.1.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000", "http://127.0.0.1:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(signals.router, prefix="/signals", tags=["signals"])
app.include_router(sentiment.router, prefix="/sentiment", tags=["sentiment"])
app.include_router(topics.router, prefix="/topics", tags=["topics"])
app.include_router(geopolitical.router, prefix="/geopolitical", tags=["geopolitical"])
app.include_router(backtest.router, prefix="/backtest", tags=["backtest"])
app.include_router(live.router, tags=["websocket"])
app.include_router(validation.router, prefix="/validation", tags=["validation"])


@app.get("/health")
async def health():
    return {"status": "ok", "version": "0.1.0"}


@app.get("/")
async def root():
    return {
        "name": "Lumina API",
        "docs": "/docs",
        "health": "/health",
    }
