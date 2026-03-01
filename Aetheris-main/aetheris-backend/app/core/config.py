"""
Aetheris — Core Configuration
Loads all settings from environment variables / .env file
"""

from pydantic_settings import BaseSettings
from typing import List
import os


class Settings(BaseSettings):
    # ── APP ─────────────────────────────────────────────────────────────────
    APP_NAME: str = "Aetheris"
    APP_VERSION: str = "1.0.0"
    DEBUG: bool = False
    SECRET_KEY: str = "aetheris-super-secret-key-change-in-production"

    # ── DATABASE ─────────────────────────────────────────────────────────────
    DATABASE_URL: str = "sqlite+aiosqlite:///./aetheris.db"
    # Production: postgresql+asyncpg://user:password@localhost/aetheris

    # ── REDIS ────────────────────────────────────────────────────────────────
    REDIS_URL: str = "redis://localhost:6379"

    # ── AI / LLM ─────────────────────────────────────────────────────────────
    ANTHROPIC_API_KEY: str = ""          # Claude API key
    OPENAI_API_KEY: str = ""             # Whisper / GPT-4o key
    GROQ_API_KEY: str = ""               # Groq API key
    LLM_MODEL: str = "llama-3.3-70b-versatile"
    LLM_MAX_TOKENS: int = 2048
    LLM_TEMPERATURE: float = 0.3

    # ── DRUG INTERACTION ─────────────────────────────────────────────────────
    OPENFDA_BASE_URL: str = "https://api.fda.gov/drug/event.json"
    RXNORM_BASE_URL: str = "https://rxnav.nlm.nih.gov/REST"

    # ── ML MODELS ────────────────────────────────────────────────────────────
    ML_MODELS_DIR: str = "./app/ml/models"
    ASA_MODEL_PATH: str = "./app/ml/models/asa_risk_model.pkl"
    COMPLICATION_MODEL_PATH: str = "./app/ml/models/complication_model.pkl"

    # ── CORS ──────────────────────────────────────────────────────────────────
    ALLOWED_ORIGINS: List[str] = [
        "http://localhost:3000",
        "http://localhost:5173",
        "http://localhost:5174",
        "http://localhost:5175",
        "http://localhost:4000",
        "https://aetheris.vercel.app",
    ]

    # ── VITALS THRESHOLDS ────────────────────────────────────────────────────
    VITALS_HR_MIN: int = 40
    VITALS_HR_MAX: int = 150
    VITALS_SPO2_CRITICAL: float = 90.0
    VITALS_SPO2_WARNING: float = 93.0
    VITALS_TEMP_HIGH: float = 38.5
    VITALS_ETCO2_MIN: float = 20.0
    VITALS_ETCO2_MAX: float = 60.0

    class Config:
        env_file = ".env"
        case_sensitive = True


settings = Settings()
