"""
Aetheris — Pre-Operative Service
Handles: AI Risk Assessment, Drug Interaction Check, Checklist Generation
"""

import httpx
import asyncio
import logging
import numpy as np
import pandas as pd
import joblib
import os
from datetime import datetime
from typing import List, Dict, Any, Optional
import uuid

from app.core.config import settings
from app.schemas import (
    PreOpAssessmentRequest, PreOpAssessmentResponse,
    DrugInteraction, RiskBreakdown, ChecklistItem
)

logger = logging.getLogger("aetheris.preop")

# ── ASA RISK SCORING ───────────────────────────────────────────────────────
SURGERY_RISK_MAP = {
    "Cardiac":      {"cardiac": 35, "anesthesia": 28, "surgical": 40},
    "Neurological": {"cardiac": 20, "anesthesia": 25, "surgical": 30},
    "Orthopedic":   {"cardiac": 12, "anesthesia": 15, "surgical": 18},
    "General":      {"cardiac": 10, "anesthesia": 12, "surgical": 15},
    "Vascular":     {"cardiac": 30, "anesthesia": 22, "surgical": 35},
    "Thoracic":     {"cardiac": 28, "anesthesia": 30, "surgical": 32},
    "Abdominal":    {"cardiac": 15, "anesthesia": 18, "surgical": 20},
    "Ophthalmic":   {"cardiac": 5,  "anesthesia": 8,  "surgical": 6},
}

def calculate_risk_scores(req: PreOpAssessmentRequest) -> Dict[str, float]:
    """Heuristic + ML hybrid risk calculation."""
    base = SURGERY_RISK_MAP.get(req.surgery_type.value, {"cardiac":10,"anesthesia":12,"surgical":15})

    # Modifiers
    cardiac    = base["cardiac"]
    anesthesia = base["anesthesia"]
    surgical   = base["surgical"]

    # Age factor
    age = getattr(req, "age", 45) # Fallback age
    # Fallback from context
    if req.cardiac_hx:  cardiac    += 20; anesthesia += 10
    if req.diabetes:    cardiac    += 8;  surgical   += 5
    if req.hypertension: cardiac   += 10; anesthesia += 5
    if req.smoking:     anesthesia += 8;  surgical   += 6

    # ASA adjustment
    asa_map = {"I":0, "II":5, "III":15, "IV":30, "V":50}
    asa_bonus = asa_map.get(req.asa_class.value if req.asa_class else "II", 5)
    cardiac    += asa_bonus * 0.4
    anesthesia += asa_bonus * 0.4
    surgical   += asa_bonus * 0.2

    # SpO2 / vitals penalties
    if req.spo2 and req.spo2 < 93:   anesthesia += 15
    if req.systolic_bp and req.systolic_bp > 160: cardiac += 10

    # ── MACHINE LEARNING HYBRID INJECTION ──
    model_path = os.path.join(os.path.dirname(__file__), '..', 'ml', 'mimic_preop_model.pkl')
    if os.path.exists(model_path):
        try:
            model = joblib.load(model_path)
            
            w = req.weight_kg if req.weight_kg else 70.0
            h = req.height_cm if req.height_cm else 170.0
            bmi = w / ((h/100.0)**2) if h > 0 else 24.0

            # Construct DataFrame matching training schema
            input_df = pd.DataFrame([{
                'Age (yrs)': age,
                'Weight (kg)': w,
                'Height (cm)': h,
                'BMI': bmi,
                'Systolic BP': req.systolic_bp if req.systolic_bp else 120.0,
                'Diastolic BP': req.diastolic_bp if req.diastolic_bp else 80.0,
                'Creatinine (mg/dL)': 1.0, # assumed median
                'eGFR (mL/min)': 90.0,     # assumed median
                'Hemoglobin (g/dL)': 14.0, # assumed median
                'Prior Surgery Count': 0,
                'Med Count': len(req.medications),
                'Gender': getattr(req, 'gender', 'Unknown'),
                'Diabetes (0/1)': '1' if req.diabetes else '0',
                'Hypertension (0/1)': '1' if req.hypertension else '0',
                'ASA Class': req.asa_class.value if req.asa_class else 'II'
            }])

            # Predict risk probability
            prob = model.predict_proba(input_df)[0][1] * 100
            
            # Blend ML probability with heuristics
            cardiac = (cardiac * 0.4) + (prob * 0.6)
            anesthesia = (anesthesia * 0.5) + (prob * 0.5)
            surgical = (surgical * 0.3) + (prob * 0.7)
            
            logger.info(f"ML Model Applied: Base Prob={prob:.2f}% -> Hybrid C:{cardiac:.1f} A:{anesthesia:.1f} S:{surgical:.1f}")

        except Exception as e:
            logger.error(f"Failed to apply ML model: {e}")

    # BMI
    bmi = None
    if req.weight_kg and req.height_cm:
        bmi = req.weight_kg / ((req.height_cm / 100) ** 2)
        if bmi > 40: anesthesia += 12; surgical += 8
        elif bmi > 30: anesthesia += 5; surgical += 3

    # Clamp to 0-100
    cardiac    = min(100, max(1, round(cardiac, 1)))
    anesthesia = min(100, max(1, round(anesthesia, 1)))
    surgical   = min(100, max(1, round(surgical, 1)))
    overall    = round((cardiac * 0.35 + anesthesia * 0.35 + surgical * 0.30), 1)

    return {
        "cardiac": cardiac,
        "anesthesia": anesthesia,
        "surgical": surgical,
        "overall": overall,
    }


def score_to_level(score: float) -> str:
    if score < 25:   return "LOW"
    elif score < 50: return "MEDIUM"
    elif score < 75: return "HIGH"
    else:            return "CRITICAL"


def predict_asa(req: PreOpAssessmentRequest) -> str:
    """Use saved ML model or fall back to heuristic."""
    try:
        from app.ml.model_service import load_asa_model, load_scaler
        import pandas as pd

        bundle = load_asa_model()
        model  = bundle["model"]
        scaler = load_scaler()

        bmi = None
        if req.weight_kg and req.height_cm:
            bmi = req.weight_kg / ((req.height_cm / 100) ** 2)

        row = {
            "age":              40,  # default — ideally passed from patient record
            "bmi":              bmi or 26,
            "weight_kg":        req.weight_kg or 75,
            "systolic_bp":      req.systolic_bp or 120,
            "diastolic_bp":     req.diastolic_bp or 80,
            "heart_rate":       req.heart_rate or 75,
            "temperature":      req.temperature or 36.8,
            "spo2":             req.spo2 or 98,
            "resp_rate":        16,
            "etco2":            38,
            "diabetes":         int(req.diabetes),
            "hypertension":     int(req.hypertension),
            "cardiac_hx":       int(req.cardiac_hx),
            "smoking":          int(req.smoking),
            "comorbidity_count": sum([req.diabetes, req.hypertension, req.cardiac_hx, req.smoking]),
            "albumin_low":      0,
            "hematocrit_low":   0,
        }
        X = pd.DataFrame([row])
        X_scaled = scaler.transform(X)
        predicted = model.predict(X_scaled)[0]
        return ["I","II","III","IV","V"][predicted - 1]
    except Exception as e:
        logger.warning(f"ML model fallback to heuristic: {e}")
        # Heuristic fallback
        score = sum([req.diabetes, req.hypertension, req.cardiac_hx, req.smoking])
        return ["I","II","III","IV","V"][min(score, 4)]


# ── DRUG INTERACTION CHECKER ───────────────────────────────────────────────
# Known dangerous interactions database (subset of OpenFDA data)
KNOWN_INTERACTIONS = [
    {"a": "warfarin",   "b": "aspirin",     "severity": "HIGH",
     "desc": "Increased bleeding risk. Consider stopping aspirin 7 days pre-op."},
    {"a": "warfarin",   "b": "ibuprofen",   "severity": "HIGH",
     "desc": "NSAIDs increase anticoagulation effect — major bleeding risk."},
    {"a": "metformin",  "b": "contrast",    "severity": "MEDIUM",
     "desc": "Hold metformin 48h before contrast imaging to prevent lactic acidosis."},
    {"a": "clopidogrel","b": "aspirin",     "severity": "MEDIUM",
     "desc": "Dual antiplatelet therapy — increased surgical bleeding. Discuss with surgeon."},
    {"a": "lisinopril", "b": "spironolactone","severity":"MEDIUM",
     "desc": "Risk of hyperkalemia. Monitor potassium levels pre-op."},
    {"a": "metoprolol", "b": "verapamil",   "severity": "HIGH",
     "desc": "Combined use can cause severe bradycardia or AV block."},
    {"a": "ssri",       "b": "tramadol",    "severity": "HIGH",
     "desc": "Serotonin syndrome risk — avoid combination or monitor closely."},
    {"a": "digoxin",    "b": "amiodarone",  "severity": "HIGH",
     "desc": "Amiodarone increases digoxin levels — risk of toxicity."},
    {"a": "sildenafil", "b": "nitrates",    "severity": "HIGH",
     "desc": "Severe hypotension — absolutely contraindicated together."},
    {"a": "lithium",    "b": "nsaid",       "severity": "MEDIUM",
     "desc": "NSAIDs reduce lithium clearance — risk of toxicity."},
]

async def check_drug_interactions(medications: List[str]) -> List[DrugInteraction]:
    """Check medications against known interaction database + OpenFDA API."""
    interactions = []
    meds_lower = [m.lower().strip() for m in medications]

    # Local DB check
    for pair in KNOWN_INTERACTIONS:
        a_found = any(pair["a"] in m for m in meds_lower)
        b_found = any(pair["b"] in m for m in meds_lower)
        if a_found and b_found:
            interactions.append(DrugInteraction(
                drug_a=pair["a"].title(),
                drug_b=pair["b"].title(),
                severity=pair["severity"],
                description=pair["desc"],
                source="Aetheris Drug DB (OpenFDA-derived)",
            ))

    # Try OpenFDA API for first medication (non-blocking)
    if medications and settings.OPENFDA_BASE_URL:
        try:
            async with httpx.AsyncClient(timeout=5.0) as client:
                primary_drug = medications[0].split()[0]
                url = f"https://api.fda.gov/drug/label.json?search=warnings:{primary_drug}&limit=1"
                resp = await client.get(url)
                if resp.status_code == 200:
                    data = resp.json()
                    # Surface warning text if available
                    results = data.get("results", [])
                    if results and "warnings" in results[0]:
                        logger.info(f"OpenFDA warning found for {primary_drug}")
        except Exception as e:
            logger.warning(f"OpenFDA API unavailable: {e}")

    return interactions


# ── PRE-OP CHECKLIST ────────────────────────────────────────────────────────
BASE_CHECKLIST = [
    {"id":1, "label":"Informed consent signed by patient",       "category":"legal",       "required":True},
    {"id":2, "label":"Blood work reviewed (CBC, BMP, coagulation)","category":"labs",      "required":True},
    {"id":3, "label":"Imaging reviewed (X-ray / MRI / CT)",      "category":"imaging",     "required":True},
    {"id":4, "label":"NPO status confirmed (nil by mouth)",       "category":"nutrition",   "required":True},
    {"id":5, "label":"Allergies verified and documented",         "category":"safety",      "required":True},
    {"id":6, "label":"IV access confirmed and patent",            "category":"access",      "required":True},
    {"id":7, "label":"Anesthesia plan reviewed and approved",     "category":"anesthesia",  "required":True},
    {"id":8, "label":"Drug interactions checked and cleared",     "category":"medication",  "required":True},
    {"id":9, "label":"Site marking completed (if applicable)",    "category":"surgical",    "required":False},
    {"id":10,"label":"Pre-op antibiotics administered",           "category":"medication",  "required":False},
]

def generate_checklist(
    surgery_type: str,
    has_drug_interactions: bool,
    risk_level: str
) -> List[ChecklistItem]:
    items = [ChecklistItem(**item, checked=False) for item in BASE_CHECKLIST]

    # Add surgery-specific items
    if surgery_type == "Cardiac":
        items.append(ChecklistItem(id=11, label="Cardiology clearance obtained", category="specialist", required=True, checked=False))
        items.append(ChecklistItem(id=12, label="Echo / stress test results reviewed", category="imaging", required=True, checked=False))
    elif surgery_type == "Neurological":
        items.append(ChecklistItem(id=11, label="Neurology consult completed", category="specialist", required=True, checked=False))
    elif surgery_type == "Orthopedic":
        items.append(ChecklistItem(id=11, label="DVT prophylaxis plan documented", category="safety", required=True, checked=False))

    if has_drug_interactions:
        items.append(ChecklistItem(id=20, label="Drug interactions reviewed with pharmacist", category="medication", required=True, checked=False))

    if risk_level in ("HIGH", "CRITICAL"):
        items.append(ChecklistItem(id=21, label="ICU bed reserved post-operatively", category="planning", required=True, checked=False))
        items.append(ChecklistItem(id=22, label="Blood products cross-matched and available", category="blood", required=True, checked=False))

    return items


# ── LLM AI SUMMARY ─────────────────────────────────────────────────────────
async def generate_ai_summary(
    req: PreOpAssessmentRequest,
    risk_scores: Dict,
    drug_interactions: List[DrugInteraction],
    asa_predicted: str,
) -> str:
    """Generate clinical AI summary using Claude API."""
    try:
        import groq
        client = groq.AsyncGroq(api_key=settings.GROQ_API_KEY)

        interactions_text = ""
        if drug_interactions:
            interactions_text = "\n".join([
                f"- {d.drug_a} + {d.drug_b}: {d.severity} — {d.description}"
                for d in drug_interactions
            ])
        else:
            interactions_text = "No significant drug interactions detected."

        prompt = f"""You are a clinical decision support AI for Aetheris surgical co-pilot system.
Generate a brief, professional pre-operative assessment summary for the surgical team.

Patient Profile:
- Surgery Type: {req.surgery_type.value}
- ASA Classification (predicted): {asa_predicted}
- Comorbidities: Diabetes={req.diabetes}, Hypertension={req.hypertension}, Cardiac Hx={req.cardiac_hx}, Smoking={req.smoking}
- Medications: {', '.join(req.medications) if req.medications else 'None listed'}

Risk Scores:
- Overall Risk: {risk_scores['overall']}% ({score_to_level(risk_scores['overall'])})
- Cardiac Risk: {risk_scores['cardiac']}%
- Anesthesia Risk: {risk_scores['anesthesia']}%
- Surgical Risk: {risk_scores['surgical']}%

Drug Interactions:
{interactions_text}

Write a 3-sentence clinical summary and one clear recommendation for the surgical team.
Be concise, factual, and use clinical language appropriate for surgeons and anesthesiologists.
"""
        message = await client.chat.completions.create(
            model=settings.LLM_MODEL,
            max_tokens=400,
            messages=[{"role": "user", "content": prompt}]
        )
        return message.choices[0].message.content

    except Exception as e:
        logger.warning(f"Claude API unavailable, using fallback summary: {e}")
        level = score_to_level(risk_scores["overall"])
        return (
            f"Patient scheduled for {req.surgery_type.value} surgery with predicted ASA Class {asa_predicted}. "
            f"Overall surgical risk is assessed as {level} ({risk_scores['overall']}%) based on clinical profile. "
            f"{'Drug interactions detected — review with pharmacist before proceeding. ' if drug_interactions else 'No significant drug interactions identified. '}"
            f"Recommendation: {'Obtain specialist clearance before proceeding.' if level in ('HIGH','CRITICAL') else 'Proceed with standard pre-operative protocol.'}"
        )


# ── MAIN SERVICE FUNCTION ──────────────────────────────────────────────────
async def run_preop_assessment(req: PreOpAssessmentRequest) -> PreOpAssessmentResponse:
    """Orchestrate the full pre-op assessment pipeline."""
    logger.info(f"Running Pre-Op assessment for patient {req.patient_id}")

    # 1. Calculate risk scores
    scores = calculate_risk_scores(req)
    risk_level = score_to_level(scores["overall"])

    # 2. Predict ASA class
    asa_predicted = predict_asa(req)

    # 3. Check drug interactions (async)
    drug_interactions = await check_drug_interactions(req.medications)

    # 4. Generate checklist
    checklist = generate_checklist(
        surgery_type=req.surgery_type.value,
        has_drug_interactions=len(drug_interactions) > 0,
        risk_level=risk_level,
    )

    # 5. AI clinical summary (async)
    ai_summary = await generate_ai_summary(req, scores, drug_interactions, asa_predicted)

    recommendation = (
        "Obtain cardiology clearance and consider ICU reservation post-operatively."
        if risk_level in ("HIGH", "CRITICAL")
        else "Proceed with standard pre-operative protocol. Ensure all checklist items are completed."
    )

    return PreOpAssessmentResponse(
        assessment_id   = str(uuid.uuid4()),
        patient_id      = req.patient_id,
        overall_risk_score = scores["overall"],
        risk_level      = risk_level,
        risk_breakdown  = RiskBreakdown(
            cardiac_risk    = scores["cardiac"],
            anesthesia_risk = scores["anesthesia"],
            surgical_risk   = scores["surgical"],
        ),
        asa_predicted      = asa_predicted,
        drug_interactions  = drug_interactions,
        checklist          = checklist,
        recommendation     = recommendation,
        ai_summary         = ai_summary,
        created_at         = datetime.utcnow(),
    )
