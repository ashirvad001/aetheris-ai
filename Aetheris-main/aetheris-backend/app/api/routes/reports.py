"""Aetheris — Report Generation Routes"""
from fastapi import APIRouter, HTTPException
from app.schemas import ReportGenerateRequest, ReportResponse, ReportSendToEHR
from app.services.postop_service import run_report_generation
from datetime import datetime

router = APIRouter()

@router.post("/generate", response_model=ReportResponse, summary="Generate AI clinical report")
async def generate_report(req: ReportGenerateRequest):
    """
    Generate an operative note or discharge summary using Claude API.
    Falls back to template-based generation if API is unavailable.
    """
    try:
        return await run_report_generation(req)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/send-to-ehr", summary="Send report to EHR system")
async def send_to_ehr(req: ReportSendToEHR):
    """Mock EHR submission endpoint. In production: integrates with Epic/Cerner via FHIR R4."""
    return {
        "report_id":    req.report_id,
        "ehr_system":   req.ehr_system,
        "status":       "sent",
        "confirmation": f"RPT-{req.report_id[:8].upper()}",
        "sent_at":      datetime.utcnow().isoformat(),
        "message":      "Report successfully submitted to EHR system.",
    }


@router.get("/types", summary="List available report types")
async def get_report_types():
    return {
        "types": [
            {"value": "operative_note",      "label": "Operative Note"},
            {"value": "discharge_summary",   "label": "Discharge Summary"},
            {"value": "risk_assessment",     "label": "Risk Assessment Report"},
            {"value": "complication_report", "label": "Complication Risk Report"},
        ]
    }
