"""Aetheris — Vitals Routes"""
from fastapi import APIRouter
from app.schemas import VitalsLogRequest
from datetime import datetime

router = APIRouter()

_vitals_history: dict = {}

@router.post("/log", summary="Log a vitals reading")
async def log_vitals(req: VitalsLogRequest):
    pid = req.patient_id
    if pid not in _vitals_history:
        _vitals_history[pid] = []
    reading = req.vitals.dict()
    reading["recorded_at"] = datetime.utcnow().isoformat()
    _vitals_history[pid].append(reading)
    # Keep last 100 readings
    _vitals_history[pid] = _vitals_history[pid][-100:]
    return {"status": "logged", "patient_id": pid, "reading": reading}

@router.get("/{patient_id}/history", summary="Get vitals history for patient")
async def get_vitals_history(patient_id: str, limit: int = 20):
    history = _vitals_history.get(patient_id, [])
    return {
        "patient_id": patient_id,
        "readings":   history[-limit:],
        "latest":     history[-1] if history else None,
        "total":      len(history),
    }
