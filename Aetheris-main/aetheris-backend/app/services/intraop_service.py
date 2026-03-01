"""
Aetheris — Intra-Operative Service
Handles: Anomaly Detection, Voice Command Processing, Vitals Analysis
"""

import logging
import asyncio
from typing import List, Dict, Optional
from datetime import datetime

from app.core.config import settings
from app.schemas import (
    VitalsReading, AnomalyCheckRequest, AnomalyResult,
    AlertCreate, AlertSeverity, VoiceCommandRequest, VoiceCommandResponse
)

logger = logging.getLogger("aetheris.intraop")


# ── VITAL THRESHOLDS ───────────────────────────────────────────────────────
THRESHOLDS = {
    "heart_rate": {
        "critical_low": 40,  "warning_low": 50,
        "warning_high": 120, "critical_high": 140,
        "unit": "bpm",
    },
    "spo2": {
        "critical_low": 90,  "warning_low": 93,
        "warning_high": 100, "critical_high": 101,   # no high threshold
        "unit": "%",
    },
    "systolic_bp": {
        "critical_low": 80,  "warning_low": 90,
        "warning_high": 160, "critical_high": 180,
        "unit": "mmHg",
    },
    "diastolic_bp": {
        "critical_low": 40,  "warning_low": 50,
        "warning_high": 100, "critical_high": 120,
        "unit": "mmHg",
    },
    "temperature": {
        "critical_low": 35.0,  "warning_low": 35.5,
        "warning_high": 38.5,  "critical_high": 39.5,
        "unit": "°C",
    },
    "etco2": {
        "critical_low": 20,  "warning_low": 25,
        "warning_high": 50,  "critical_high": 60,
        "unit": "mmHg",
    },
    "resp_rate": {
        "critical_low": 8,   "warning_low": 10,
        "warning_high": 25,  "critical_high": 30,
        "unit": "br/min",
    },
}


# ── ANOMALY DETECTION ──────────────────────────────────────────────────────
def check_vital_status(name: str, value: float) -> str:
    """Returns: 'normal', 'warning_low', 'warning_high', 'critical_low', 'critical_high'"""
    t = THRESHOLDS.get(name, {})
    if not t:
        return "normal"
    if value <= t.get("critical_low", -999):    return "critical_low"
    if value >= t.get("critical_high", 99999):  return "critical_high"
    if value <= t.get("warning_low", -999):     return "warning_low"
    if value >= t.get("warning_high", 99999):   return "warning_high"
    return "normal"


def build_alert(
    patient_id: str,
    surgery_id: Optional[str],
    vital_name: str,
    value: float,
    status: str,
) -> Optional[AlertCreate]:
    """Build an alert object from a threshold breach."""
    t = THRESHOLDS.get(vital_name, {})
    unit = t.get("unit", "")
    is_critical = "critical" in status
    is_low      = "low" in status

    severity = AlertSeverity.CRITICAL if is_critical else AlertSeverity.WARNING
    direction = "dropped below" if is_low else "exceeded"
    threshold_val = (
        t.get("critical_low") if is_critical and is_low else
        t.get("critical_high") if is_critical and not is_low else
        t.get("warning_low") if is_low else
        t.get("warning_high")
    )

    vital_display = vital_name.replace("_", " ").title()
    title   = f"{'🚨 CRITICAL' if is_critical else '⚠️ WARNING'}: {vital_display}"
    message = (
        f"{vital_display} has {direction} threshold: "
        f"{value:.1f} {unit} "
        f"({'threshold: ' + str(threshold_val) + ' ' + unit}). "
        f"{'Immediate clinical attention required.' if is_critical else 'Monitor closely.'}"
    )

    return AlertCreate(
        patient_id  = patient_id,
        surgery_id  = surgery_id,
        severity    = severity,
        title       = title,
        message     = message,
        vital_type  = vital_name,
        vital_value = value,
    )


def analyze_anomalies(req: AnomalyCheckRequest) -> AnomalyResult:
    """Check all vitals against thresholds and return fired alerts."""
    v = req.vitals
    vitals_dict = {
        "heart_rate":   v.heart_rate,
        "spo2":         v.spo2,
        "systolic_bp":  v.systolic_bp,
        "diastolic_bp": v.diastolic_bp,
        "temperature":  v.temperature,
        "etco2":        v.etco2,
        "resp_rate":    v.resp_rate,
    }

    alerts_fired: List[AlertCreate] = []
    vitals_status: Dict[str, str] = {}

    for name, value in vitals_dict.items():
        status = check_vital_status(name, value)
        vitals_status[name] = status
        if status != "normal":
            alert = build_alert(req.patient_id, req.surgery_id, name, value, status)
            if alert:
                alerts_fired.append(alert)

    return AnomalyResult(
        has_anomaly   = len(alerts_fired) > 0,
        alerts_fired  = alerts_fired,
        vitals_status = vitals_status,
    )


# ── VOICE COMMAND PROCESSOR ────────────────────────────────────────────────
# Procedure steps for the timeline
PROCEDURE_STEPS = [
    "Pre-Procedure Setup",
    "Anesthesia Induction",
    "Incision & Access",
    "Main Procedure Phase",
    "Hemostasis & Verification",
    "Closure",
    "Recovery Handoff",
]

async def transcribe_audio(audio_b64: str = None, file_path: str = None) -> str:
    """Transcribe audio using Groq Whisper API."""
    try:
        import base64, tempfile, os
        from groq import Groq

        # Support base64 or direct file
        tmp_path = file_path
        created_temp = False

        if not tmp_path and audio_b64:
            audio_bytes = base64.b64decode(audio_b64)
            with tempfile.NamedTemporaryFile(suffix=".webm", delete=False) as tmp:
                tmp.write(audio_bytes)
                tmp_path = tmp.name
                created_temp = True

        if not tmp_path:
            return ""

        client = Groq(api_key=settings.GROQ_API_KEY)
        
        with open(tmp_path, "rb") as file:
            transcription = client.audio.transcriptions.create(
              file=(os.path.basename(tmp_path), file.read()),
              model="whisper-large-v3-turbo",
            )
            
        if created_temp:
            os.unlink(tmp_path)

        return transcription.text
    except Exception as e:
        logger.warning(f"Groq Whisper API error: {e}")
    return ""


async def process_voice_command(
    req: VoiceCommandRequest,
    current_vitals: Optional[Dict] = None,
) -> VoiceCommandResponse:
    """Transcribe voice or use text, pass to LLM, generate clinical response."""

    # 1. Get transcription
    transcription = req.text_query or ""
    if req.audio_b64 and not transcription:
        transcription = await transcribe_audio(req.audio_b64)
    if not transcription:
        transcription = "..."

    # 2. Ask the powerful Groq LLM
    response = await ask_llm_assistant(transcription, current_vitals)

    return VoiceCommandResponse(
        transcription = transcription,
        response      = response,
        vitals_cited  = current_vitals,
    )


async def ask_llm_assistant(query: str, vitals: Optional[Dict]) -> str:
    """Pass query to Groq LLM acting as Aetheris AI co-pilot."""
    if query == "...": return "Please say or type a command."
    try:
        import groq
        client = groq.AsyncGroq(api_key=settings.GROQ_API_KEY)

        vitals_context = ""
        if vitals:
            vitals_context = f"\n\nCURRENT VITALS:\n{vitals}"

        system_prompt = (
            "You are Aetheris, an advanced surgical AI co-pilot and project assistant. "
            "You help surgeons monitor patients during intra-op and can answer general questions "
            "about this tech project, the patient, or medical procedures. Keep responses concise, "
            "conversational, and helpful. Always refer to the current vitals if asked about them."
            f"{vitals_context}"
        )

        message = await client.chat.completions.create(
            model=settings.LLM_MODEL,
            max_tokens=250,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": query}
            ]
        )
        return message.choices[0].message.content
    except Exception as e:
        logger.warning(f"Groq LLM Chatbot failed: {e}")
        return "I'm having trouble connecting to my AI brain at the moment."
