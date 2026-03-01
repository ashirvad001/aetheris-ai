"""
Aetheris — Multimodal Perioperative Co-Pilot
FastAPI Backend Entry Point
"""

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.trustedhost import TrustedHostMiddleware
from contextlib import asynccontextmanager
import logging

from app.api.routes import preop, intraop, postop, reports, vitals, patients, alerts
from app.core.config import settings
from app.core.database import init_db

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("aetheris")


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Startup and shutdown events."""
    logger.info("🚀 Aetheris Backend Starting...")
    await init_db()
    logger.info("✅ Database initialized")
    yield
    logger.info("🛑 Aetheris Backend Shutting down...")


app = FastAPI(
    title="Aetheris API",
    description="AI-Powered Multimodal Perioperative Co-Pilot Backend",
    version="1.0.0",
    docs_url="/docs",
    redoc_url="/redoc",
    lifespan=lifespan,
)

# ── CORS ───────────────────────────────────────────────────────────────────
app.add_middleware(
    CORSMiddleware,
    allow_origin_regex=".*",
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ── ROUTERS ────────────────────────────────────────────────────────────────
app.include_router(patients.router,  prefix="/api/patients",  tags=["Patients"])
app.include_router(preop.router,     prefix="/api/preop",     tags=["Pre-Operative"])
app.include_router(intraop.router,   prefix="/api/intraop",   tags=["Intra-Operative"])
app.include_router(postop.router,    prefix="/api/postop",    tags=["Post-Operative"])
app.include_router(vitals.router,    prefix="/api/vitals",    tags=["Vitals"])
app.include_router(reports.router,   prefix="/api/reports",   tags=["Reports"])
app.include_router(alerts.router,    prefix="/api/alerts",    tags=["Alerts"])


@app.get("/", tags=["Health"])
async def root():
    return {
        "system": "Aetheris Perioperative Co-Pilot",
        "version": "1.0.0",
        "status": "operational",
    }


@app.get("/health", tags=["Health"])
async def health_check():
    return {"status": "healthy", "api": "online"}
