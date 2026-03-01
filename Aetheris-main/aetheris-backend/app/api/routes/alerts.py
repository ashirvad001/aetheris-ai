"""Aetheris — Alerts Routes"""
from fastapi import APIRouter, HTTPException
from app.schemas import AlertCreate, AlertResponse, AcknowledgeRequest
from datetime import datetime
import uuid

router = APIRouter()

_alerts: dict = {
    "a001": {
        "id": "a001",
        "patient_id": "p001",
        "surgery_id": "s001",
        "severity": "High",
        "title": "Abnormal Heart Rate",
        "message": "Heart rate has exceeded 120 bpm.",
        "vital_type": "heart_rate",
        "vital_value": 125,
        "acknowledged": False,
        "created_at": datetime.utcnow().isoformat()
    }
}

@router.get("/", summary="Get all alerts")
async def get_alerts(patient_id: str = None, unread_only: bool = False):
    alerts = list(_alerts.values())
    if patient_id:
        alerts = [a for a in alerts if a["patient_id"] == patient_id]
    if unread_only:
        alerts = [a for a in alerts if not a["acknowledged"]]
    return {"alerts": sorted(alerts, key=lambda x: x["created_at"], reverse=True), "total": len(alerts)}

@router.post("/", response_model=AlertResponse, summary="Create an alert")
async def create_alert(req: AlertCreate):
    aid = str(uuid.uuid4())
    alert = {
        "id": aid, **req.dict(),
        "acknowledged": False,
        "created_at": datetime.utcnow().isoformat()
    }
    _alerts[aid] = alert
    return alert

@router.patch("/{alert_id}/acknowledge", summary="Acknowledge an alert")
async def acknowledge_alert(alert_id: str, req: AcknowledgeRequest):
    if alert_id not in _alerts:
        raise HTTPException(status_code=404, detail="Alert not found")
    _alerts[alert_id]["acknowledged"] = True
    _alerts[alert_id]["acknowledged_by"] = req.acknowledged_by
    return {"status": "acknowledged", "alert_id": alert_id}

@router.delete("/acknowledge-all", summary="Acknowledge all alerts")
async def acknowledge_all(patient_id: str = None):
    count = 0
    for alert in _alerts.values():
        if not patient_id or alert["patient_id"] == patient_id:
            alert["acknowledged"] = True
            count += 1
    return {"acknowledged_count": count}
