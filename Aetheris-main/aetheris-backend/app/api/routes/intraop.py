"""
Aetheris — API Routes: Intra-Operative
POST /api/intraop/anomaly-check
POST /api/intraop/voice-command
PATCH /api/intraop/procedure-step
WS   /api/intraop/vitals-stream/{patient_id}
"""
import asyncio
import json
import random
import math
from datetime import datetime
from fastapi import APIRouter, HTTPException, WebSocket, WebSocketDisconnect, UploadFile, File, Form
import tempfile
import os

from app.schemas import (
    AnomalyCheckRequest, AnomalyResult,
    VoiceCommandRequest, VoiceCommandResponse,
    ProcedureStepUpdate
)
from app.services.intraop_service import analyze_anomalies, process_voice_command

router = APIRouter()

# ── REST ENDPOINTS ─────────────────────────────────────────────────────────
@router.post("/anomaly-check", response_model=AnomalyResult, summary="Check vitals for anomalies")
async def check_anomaly(req: AnomalyCheckRequest):
    """
    Analyze a vitals reading and return any threshold breach alerts.
    Call this every time new vitals data arrives from OR monitoring equipment.
    """
    try:
        return analyze_anomalies(req)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/voice-command", response_model=VoiceCommandResponse, summary="Process surgeon voice command")
async def voice_command(req: VoiceCommandRequest):
    """
    Process audio or text query from surgeon.
    Supports: vitals queries, procedure status, medication info.
    Audio: send base64-encoded audio in audio_b64 field.
    Text: send query in text_query field (faster, no Whisper needed).
    """
    try:
        # Use mock vitals for demo; in production, fetch from live stream
        mock_vitals = {
            "heart_rate": 76, "spo2": 97.5,
            "systolic_bp": 122, "diastolic_bp": 79,
            "temperature": 36.8, "etco2": 38.0, "resp_rate": 14,
        }
        return await process_voice_command(req, current_vitals=mock_vitals)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/voice-command-audio", response_model=VoiceCommandResponse, summary="Process uploaded audio command")
async def voice_command_audio(patient_id: str = Form(...), audio_file: UploadFile = File(...)):
    """Receives a raw WebM file, transcribes it, and processes the voice command."""
    try:
        # Save temp file
        with tempfile.NamedTemporaryFile(delete=False, suffix=".webm") as tmp:
            tmp.write(await audio_file.read())
            tmp_path = tmp.name

        from app.services.intraop_service import transcribe_audio
        transcription = await transcribe_audio(file_path=tmp_path)
        os.unlink(tmp_path)

        req = VoiceCommandRequest(patient_id=patient_id, text_query=transcription)
        
        mock_vitals = {
            "heart_rate": 76, "spo2": 97.5,
            "systolic_bp": 122, "diastolic_bp": 79,
            "temperature": 36.8, "etco2": 38.0, "resp_rate": 14,
        }
        return await process_voice_command(req, current_vitals=mock_vitals)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/text-command", response_model=VoiceCommandResponse, summary="Process text chat command")
async def text_command(req: VoiceCommandRequest):
    """Fallback endpoint for when the user types text instead of using voice."""
    try:
        from app.services.intraop_service import process_voice_command
        # Pass mock vitals matching the audio route
        mock_vitals = {
            "heart_rate": 76, "spo2": 97.5,
            "systolic_bp": 122, "diastolic_bp": 79,
            "temperature": 36.8, "etco2": 38.0, "resp_rate": 14,
        }
        return await process_voice_command(req, current_vitals=mock_vitals)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.patch("/procedure-step", summary="Advance procedure timeline step")
async def update_procedure_step(req: ProcedureStepUpdate):
    """Update the current step of the procedure timeline."""
    from app.services.intraop_service import PROCEDURE_STEPS
    if req.current_step >= len(PROCEDURE_STEPS):
        raise HTTPException(status_code=400, detail="Step index out of range")
    return {
        "surgery_id":   req.surgery_id,
        "current_step": req.current_step,
        "step_name":    PROCEDURE_STEPS[req.current_step],
        "updated_at":   datetime.utcnow().isoformat(),
    }


@router.get("/procedure-steps", summary="Get all procedure step labels")
async def get_procedure_steps():
    from app.services.intraop_service import PROCEDURE_STEPS
    return {"steps": PROCEDURE_STEPS}


# ── WEBSOCKET: LIVE VITALS STREAM ──────────────────────────────────────────
def simulate_vitals(t: int, patient_id: str) -> dict:
    """
    Simulate realistic live vitals with sinusoidal variation + noise.
    In production: replace with real IoT device data.
    """
    # Use patient_id as seed offset for variety between patients
    seed_offset = sum(ord(c) for c in patient_id) % 20

    hr   = 75 + 8 * math.sin(t * 0.05 + seed_offset) + random.gauss(0, 1.5)
    spo2 = 97.5 + 1.5 * math.sin(t * 0.03) + random.gauss(0, 0.3)
    sbp  = 120 + 12 * math.sin(t * 0.04 + 1) + random.gauss(0, 2)
    dbp  = 78  + 8  * math.sin(t * 0.04 + 1) + random.gauss(0, 1.5)
    temp = 36.8 + 0.3 * math.sin(t * 0.02) + random.gauss(0, 0.05)
    etco2 = 38 + 4 * math.sin(t * 0.06) + random.gauss(0, 0.8)
    rr   = 15 + 3 * math.sin(t * 0.03) + random.gauss(0, 0.5)

    # Clamp values to clinical ranges
    vitals = {
        "heart_rate":   round(max(40, min(160, hr)), 1),
        "spo2":         round(max(85, min(100, spo2)), 1),
        "systolic_bp":  round(max(70, min(200, sbp)), 1),
        "diastolic_bp": round(max(40, min(130, dbp)), 1),
        "temperature":  round(max(35.0, min(40.5, temp)), 2),
        "etco2":        round(max(15, min(70, etco2)), 1),
        "resp_rate":    round(max(6, min(35, rr)), 1),
        "timestamp":    datetime.utcnow().isoformat(),
        "patient_id":   patient_id,
    }

    # Determine overall status
    status = "normal"
    if vitals["spo2"] < 90 or vitals["heart_rate"] > 135 or vitals["heart_rate"] < 45:
        status = "critical"
    elif vitals["spo2"] < 93 or vitals["systolic_bp"] > 160:
        status = "warning"
    vitals["status"] = status

    return vitals


@router.websocket("/vitals-stream/{patient_id}")
async def vitals_stream(websocket: WebSocket, patient_id: str):
    """
    WebSocket endpoint for live vitals streaming.
    Sends a new vitals reading every 1.5 seconds.

    Frontend usage:
        const ws = new WebSocket(`ws://localhost:8000/api/intraop/vitals-stream/${patientId}`);
        ws.onmessage = (e) => { const vitals = JSON.parse(e.data); /* update UI */ };
    """
    await websocket.accept()
    t = 0
    try:
        while True:
            vitals = simulate_vitals(t, patient_id)
            await websocket.send_text(json.dumps(vitals))

            # Auto-trigger anomaly check every tick
            from app.schemas import AnomalyCheckRequest, VitalsReading
            check = AnomalyCheckRequest(
                patient_id=patient_id,
                vitals=VitalsReading(**{k:v for k,v in vitals.items()
                                        if k not in ("timestamp","patient_id","status")})
            )
            result = analyze_anomalies(check)
            if result.has_anomaly:
                await websocket.send_text(json.dumps({
                    "type": "ANOMALY_ALERT",
                    "alerts": [a.model_dump(mode='json') for a in result.alerts_fired],
                }))

            t += 1
            await asyncio.sleep(1.5)

    except WebSocketDisconnect:
        pass
    except Exception as e:
        await websocket.close(code=1011, reason=str(e))
