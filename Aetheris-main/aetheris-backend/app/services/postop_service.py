"""
Aetheris — Post-Operative Service
Handles: Complication Risk Prediction, Operative Note Generation, Discharge Summary
"""

import logging
import uuid
from datetime import datetime
from typing import Optional, List

from app.core.config import settings
from app.schemas import (
    ComplicationRiskRequest, ComplicationRiskResponse, ComplicationRisk,
    ReportGenerateRequest, ReportResponse, ReportType
)

logger = logging.getLogger("aetheris.postop")


# ── COMPLICATION RISK PREDICTOR ────────────────────────────────────────────
SURGERY_COMPLICATION_BASE = {
    "Cardiac":      {"dvt":18, "infection":12, "pneumonia":25, "readmission":20},
    "Orthopedic":   {"dvt":22, "infection":8,  "pneumonia":12, "readmission":15},
    "Neurological": {"dvt":14, "infection":10, "pneumonia":18, "readmission":17},
    "General":      {"dvt":10, "infection":8,  "pneumonia":10, "readmission":12},
    "Vascular":     {"dvt":20, "infection":14, "pneumonia":20, "readmission":22},
    "Thoracic":     {"dvt":16, "infection":12, "pneumonia":30, "readmission":18},
    "Abdominal":    {"dvt":12, "infection":15, "pneumonia":14, "readmission":16},
    "Ophthalmic":   {"dvt":3,  "infection":4,  "pneumonia":4,  "readmission":5},
}

def risk_to_level(pct: float) -> str:
    if pct < 10:  return "LOW"
    elif pct < 25: return "MEDIUM"
    else:          return "HIGH"

def predict_complications(req: ComplicationRiskRequest) -> ComplicationRiskResponse:
    """Heuristic + ML hybrid complication risk prediction."""
    import random
    try:
        # Try ML model first
        from app.ml.model_service import load_complication_model
        import pandas as pd

        bundle  = load_complication_model()
        model   = bundle["model"]
        features = bundle["features"]
        targets  = bundle["targets"]

        # Compute BMI dynamically from patient data
        bmi = 26.0  # fallback
        if req.weight_kg and req.height_cm and req.height_cm > 0:
            bmi = round(req.weight_kg / ((req.height_cm / 100) ** 2), 1)

        # Add small clinical variation to simulate real-world variance
        age_val = req.age or 55
        duration_val = req.duration_min or 150
        blood_loss_val = req.blood_loss_ml or 300

        row = {
            "age":                    age_val,
            "bmi":                    bmi,
            "surgery_duration_min":   duration_val + random.randint(-10, 10),
            "blood_loss_ml":          blood_loss_val + random.randint(-30, 30),
            "asa_class":              {"I":1,"II":2,"III":3,"IV":4,"V":5}.get(req.asa_class or "II", 2),
            "diabetes":               int(req.diabetes),
            "hypertension":           int(req.hypertension),
            "cardiac_hx":             int(req.cardiac_hx),
            "smoker":                 int(req.smoker),
            "surgery_type_cardiac":   int(req.surgery_type.value == "Cardiac"),
            "surgery_type_orthopedic":int(req.surgery_type.value == "Orthopedic"),
            "surgery_type_neuro":     int(req.surgery_type.value == "Neurological"),
        }
        X   = pd.DataFrame([row])
        preds = model.predict(X)[0]
        dvt, infection, pneumonia, readmission = [round(float(p), 1) for p in preds]

    except Exception as e:
        logger.warning(f"Complication ML model fallback: {e}")
        # Heuristic fallback
        base = SURGERY_COMPLICATION_BASE.get(req.surgery_type.value,
               {"dvt":10,"infection":8,"pneumonia":10,"readmission":12})
        mod = 1.0
        if req.diabetes:    mod += 0.3
        if req.cardiac_hx:  mod += 0.4
        if req.hypertension: mod += 0.15
        if req.smoker:      mod += 0.2
        asa_map = {"I":0.7,"II":1.0,"III":1.4,"IV":2.0,"V":3.0}
        mod *= asa_map.get(req.asa_class or "II", 1.0)
        if req.duration_min and req.duration_min > 240: mod += 0.2
        if req.blood_loss_ml and req.blood_loss_ml > 500: mod += 0.25

        dvt          = round(min(base["dvt"]        * mod, 75), 1)
        infection    = round(min(base["infection"]   * mod, 60), 1)
        pneumonia    = round(min(base["pneumonia"]   * mod, 70), 1)
        readmission  = round(min(base["readmission"] * mod, 60), 1)

    overall = round((dvt * 0.25 + infection * 0.25 + pneumonia * 0.25 + readmission * 0.25), 1)
    overall_level = risk_to_level(overall)

    complications = [
        ComplicationRisk(
            name="Deep Vein Thrombosis (DVT)",
            risk_pct=dvt,
            risk_level=risk_to_level(dvt),
            description="Blood clot formation risk in deep veins post-surgery.",
        ),
        ComplicationRisk(
            name="Surgical Site Infection",
            risk_pct=infection,
            risk_level=risk_to_level(infection),
            description="Risk of infection at the incision site or deeper tissues.",
        ),
        ComplicationRisk(
            name="Post-Op Pneumonia",
            risk_pct=pneumonia,
            risk_level=risk_to_level(pneumonia),
            description="Pulmonary complication from reduced mobility and ventilation.",
        ),
        ComplicationRisk(
            name="30-Day Readmission",
            risk_pct=readmission,
            risk_level=risk_to_level(readmission),
            description="Probability of hospital readmission within 30 days of discharge.",
        ),
    ]

    recommendation = (
        "High complication risk detected. Recommend ICU monitoring, early mobilization, "
        "prophylactic anticoagulation, and daily wound inspection."
        if overall_level == "HIGH"
        else "Standard post-operative monitoring protocol. Follow discharge instructions and schedule follow-up."
    )

    return ComplicationRiskResponse(
        patient_id    = req.patient_id,
        overall_score = overall,
        risk_level    = overall_level,
        complications = complications,
        recommendation = recommendation,
    )


# ── REPORT GENERATION ──────────────────────────────────────────────────────
OPERATIVE_NOTE_TEMPLATE = """
OPERATIVE NOTE
==============
Date: {date}
Patient Name: {patient_name}
Patient ID: {patient_id}
Procedure: {surgery_type}
Surgeon: {surgeon}
Anesthesiologist: {anesthesiologist}
OR Room: {or_room}

PREOPERATIVE DIAGNOSIS:
{preop_diagnosis}

POSTOPERATIVE DIAGNOSIS:
Same as preoperative.

PROCEDURE PERFORMED:
{surgery_type} under {anesthesia_type} anesthesia.

OPERATIVE DETAILS:
The patient was brought to the operating room and positioned appropriately.
Standard monitoring was applied including continuous ECG, pulse oximetry,
end-tidal CO2, and invasive blood pressure monitoring.

Anesthesia was induced without complication. The operative site was
prepped and draped in a sterile fashion.

Procedure performed as planned. Total operative time: {duration} minutes.
Estimated blood loss: {blood_loss} mL. No intraoperative complications noted.

Wound was closed in layers with appropriate suture material.
Final sponge, needle, and instrument counts were correct.

DISPOSITION:
Patient transferred to {disposition} in stable condition.

ATTENDING SURGEON SIGNATURE: ___________________________
Date/Time: {date}
""".strip()


DISCHARGE_SUMMARY_TEMPLATE = """
DISCHARGE SUMMARY
=================
Date of Discharge: {date}
Patient Name: {patient_name}
Patient ID: {patient_id}
Procedure: {surgery_type}
Admitting Surgeon: {surgeon}

HOSPITAL COURSE:
Patient underwent {surgery_type} without significant intraoperative complications.
Post-operative recovery was {recovery_status}. Pain was managed with {pain_mgmt}.

DISCHARGE CONDITION:
Stable. Vital signs within normal limits at time of discharge.

DISCHARGE MEDICATIONS:
{medications}

DISCHARGE INSTRUCTIONS:
1. Rest and limit physical activity for {rest_days} days.
2. No driving or operating heavy machinery for 48 hours post-anesthesia.
3. Keep wound site clean and dry. Change dressing as instructed.
4. Diet: {diet_instructions}
5. Contact surgeon immediately if fever >38.5°C, increased redness/swelling, or wound discharge.

FOLLOW-UP APPOINTMENT:
Schedule with your surgeon in {followup_days} days.
Emergency contact: Hospital main line or nearest emergency department.

DISCHARGE PHYSICIAN: ___________________________
""".strip()


async def generate_report_with_llm(
    req: ReportGenerateRequest,
    patient_data: dict,
    surgery_data: dict,
) -> str:
    """Use Claude API to generate a clinical report."""
    try:
        import groq
        client = groq.AsyncGroq(api_key=settings.GROQ_API_KEY)

        if req.report_type == ReportType.OPERATIVE_NOTE:
            prompt = f"""Generate a professional operative note for the following surgery.
Use standard clinical format. Be concise but complete.
CRITICAL: Produce the report ONLY for the patient name '{patient_data.get('name', 'Unknown')}'. Do NOT hallucinate any other patient name.

Patient: {patient_data.get('name', 'N/A')}, Age: {patient_data.get('age', 'N/A')}
Surgery: {surgery_data.get('surgery_type', 'N/A')}
Surgeon: {surgery_data.get('surgeon_name', 'N/A')}
Duration: {surgery_data.get('duration_minutes', 'N/A')} minutes
Blood loss: {surgery_data.get('estimated_blood_loss_ml', 'N/A')} mL
Additional notes: {req.extra_notes or 'None'}

Write a complete operative note with sections: Preoperative Diagnosis, 
Postoperative Diagnosis, Procedure Performed, Operative Details, Disposition.
"""
        elif req.report_type == ReportType.DISCHARGE_SUMMARY:
            prompt = f"""Generate a professional discharge summary.
CRITICAL: Produce the report ONLY for the patient name '{patient_data.get('name', 'Unknown')}'. Do NOT hallucinate or guess any other patient name.

Patient: {patient_data.get('name', 'N/A')}, Age: {patient_data.get('age', 'N/A')}
Procedure: {surgery_data.get('surgery_type', 'N/A')}
Additional notes: {req.extra_notes or 'None'}

Write a complete discharge summary with sections: Hospital Course, 
Discharge Condition, Discharge Medications, Instructions, Follow-up.
"""
        else:
            prompt = f"Generate a {req.report_type.value} report for patient {req.patient_id}."

        message = await client.chat.completions.create(
            model=settings.LLM_MODEL,
            max_tokens=settings.LLM_MAX_TOKENS,
            messages=[{"role": "user", "content": prompt}]
        )
        return message.choices[0].message.content

    except Exception as e:
        logger.warning(f"Claude API unavailable for report: {e}")
        # Return template-based fallback
        return generate_template_report(req, patient_data, surgery_data)


def generate_template_report(req, patient_data: dict, surgery_data: dict) -> str:
    """Template-based report fallback when LLM is unavailable."""
    now = datetime.utcnow().strftime("%B %d, %Y %H:%M UTC")

    if req.report_type == ReportType.OPERATIVE_NOTE:
        return OPERATIVE_NOTE_TEMPLATE.format(
            date=now,
            patient_name=patient_data.get("name", "Unknown Patient"),
            patient_id=req.patient_id,
            surgery_type=surgery_data.get("surgery_type", "Surgical Procedure"),
            surgeon=surgery_data.get("surgeon_name", "Attending Surgeon"),
            anesthesiologist=surgery_data.get("anesthesiologist", "Anesthesiologist"),
            or_room=surgery_data.get("or_room", "OR Suite"),
            preop_diagnosis=f"Patient scheduled for {surgery_data.get('surgery_type','procedure')}",
            anesthesia_type="general",
            duration=surgery_data.get("duration_minutes", "N/A"),
            blood_loss=surgery_data.get("estimated_blood_loss_ml", "N/A"),
            disposition="Post-Anesthesia Care Unit (PACU)",
        )
    else:
        return DISCHARGE_SUMMARY_TEMPLATE.format(
            date=now,
            patient_name=patient_data.get("name", "Unknown Patient"),
            patient_id=req.patient_id,
            surgery_type=surgery_data.get("surgery_type", "Surgical Procedure"),
            surgeon=surgery_data.get("surgeon_name", "Attending Surgeon"),
            recovery_status="uneventful",
            pain_mgmt="multimodal analgesia protocol",
            medications="As prescribed. Review with your pharmacist.",
            rest_days=7,
            diet_instructions="Regular diet. Stay well hydrated.",
            followup_days=14,
        )


async def run_report_generation(req: ReportGenerateRequest) -> ReportResponse:
    """Orchestrate full report generation pipeline."""
    logger.info(f"Generating {req.report_type} for patient {req.patient_id}")

    # Mock patient/surgery data (in production: fetch from DB)
    patient_data = {
        "name": req.patient_name or "Patient", 
        "age": req.patient_age or "N/A",
        "id": req.patient_id,
    }
    surgery_data = {
        "surgery_type": req.surgery_name or "Surgical Procedure",
        "surgeon_name": "Dr. Attending Surgeon",
        "anesthesiologist": "Anesthesiologist",
        "or_room": "OR-1",
        "duration_minutes": 180,
        "estimated_blood_loss_ml": 300,
    }

    content = await generate_report_with_llm(req, patient_data, surgery_data)

    titles = {
        ReportType.OPERATIVE_NOTE:      "Operative Note",
        ReportType.DISCHARGE_SUMMARY:   "Discharge Summary",
        ReportType.RISK_ASSESSMENT:     "Pre-Op Risk Assessment Report",
        ReportType.COMPLICATION_REPORT: "Complication Risk Report",
    }

    return ReportResponse(
        id          = str(uuid.uuid4()),
        patient_id  = req.patient_id,
        surgery_id  = req.surgery_id,
        report_type = req.report_type.value,
        title       = titles.get(req.report_type, "Clinical Report"),
        content     = content,
        status      = "draft",
        created_at  = datetime.utcnow(),
    )
