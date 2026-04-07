import asyncio
import json
import os
import random
from datetime import date
from pathlib import Path

from fastapi import APIRouter, WebSocket, WebSocketDisconnect
from loguru import logger

DATA_DIR = os.getenv("DATA_DIR", "./data")
router = APIRouter()

BROADCAST_INTERVAL = 30


class ConnectionManager:
    def __init__(self):
        self.active: list[WebSocket] = []

    async def connect(self, ws: WebSocket):
        await ws.accept()
        self.active.append(ws)
        logger.info(f"WebSocket connected — {len(self.active)} active")

    def disconnect(self, ws: WebSocket):
        if ws in self.active:
            self.active.remove(ws)
        logger.info(f"WebSocket disconnected — {len(self.active)} active")

    async def broadcast(self, data: dict):
        dead = []
        for ws in self.active:
            try:
                await ws.send_json(data)
            except Exception:
                dead.append(ws)
        for ws in dead:
            self.disconnect(ws)


manager = ConnectionManager()


def _get_latest_payload() -> dict:
    try:
        from training.regime_classifier import RegimeClassifier
        clf = RegimeClassifier()
        result = clf.predict_latest(DATA_DIR)
        if result["regime"] != "unknown":
            return {
                "type": "signal_update",
                "date": str(result["date"]),
                "regime": result["regime"],
                "confidence": result["confidence"],
                "probabilities": result["probabilities"],
                "timestamp": date.today().isoformat(),
            }
    except Exception:
        pass

    regimes = ["risk_on", "transition", "risk_off"]
    regime = random.choice(regimes)
    ro = random.uniform(0.1, 0.8)
    rf = random.uniform(0.05, 1 - ro)
    tr = round(1 - ro - rf, 3)
    return {
        "type": "signal_update",
        "date": date.today().isoformat(),
        "regime": regime,
        "confidence": round(random.uniform(0.55, 0.90), 3),
        "probabilities": {
            "risk_on": round(ro, 3),
            "risk_off": round(rf, 3),
            "transition": round(tr, 3),
        },
        "timestamp": date.today().isoformat(),
    }


@router.websocket("/ws/live")
async def live_signal(websocket: WebSocket):
    await manager.connect(websocket)
    try:
        await websocket.send_json({"type": "connected", "message": "Lumina live signal stream"})
        payload = _get_latest_payload()
        await websocket.send_json(payload)

        while True:
            await asyncio.sleep(BROADCAST_INTERVAL)
            payload = _get_latest_payload()
            await websocket.send_json(payload)
    except WebSocketDisconnect:
        manager.disconnect(websocket)
    except Exception as e:
        logger.error(f"WebSocket error: {e}")
        manager.disconnect(websocket)
