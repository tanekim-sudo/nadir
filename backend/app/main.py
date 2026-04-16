"""NADIR — Narrative Adversarial Detection and Investment Recognition."""
import logging

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.core.config import get_settings
from app.routers import (
    alerts,
    analytics_router,
    beliefs,
    nadir,
    positions,
    predictions,
    signals,
    universe,
)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)

settings = get_settings()

app = FastAPI(
    title="NADIR",
    description="Narrative Adversarial Detection and Investment Recognition",
    version="1.0.0",
    docs_url="/api/docs",
    redoc_url="/api/redoc",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origin_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(universe.router)
app.include_router(signals.router)
app.include_router(nadir.router)
app.include_router(beliefs.router)
app.include_router(positions.router)
app.include_router(predictions.router)
app.include_router(alerts.router)
app.include_router(analytics_router.router)


@app.get("/api/health")
def health_check():
    db_ok = False
    try:
        from app.db.session import _get_engine
        with _get_engine().connect() as conn:
            conn.execute(__import__("sqlalchemy").text("SELECT 1"))
            db_ok = True
    except Exception:
        pass
    return {
        "status": "healthy",
        "db_connected": db_ok,
        "mode": "paper" if not settings.alpaca_live else "LIVE",
        "version": "2.0.0",
    }
