"""
Aetheris — API Routes: Pre-Operative
POST /api/preop/assess
"""
from fastapi import APIRouter, HTTPException
from app.schemas import PreOpAssessmentRequest, PreOpAssessmentResponse
from app.services.preop_service import run_preop_assessment

router = APIRouter()

@router.post("/assess", response_model=PreOpAssessmentResponse, summary="Run AI Pre-Op Assessment")
async def assess_patient(req: PreOpAssessmentRequest):
    """
    Full pre-operative AI assessment pipeline:
    - ASA risk scoring (ML model)
    - Drug interaction checking (OpenFDA)
    - Pre-op checklist generation
    - AI clinical summary (Claude API)
    """
    try:
        return await run_preop_assessment(req)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/checklist/templates", summary="Get standard checklist templates")
async def get_checklist_templates():
    """Return base checklist templates for all surgery types."""
    from app.services.preop_service import BASE_CHECKLIST, SURGERY_RISK_MAP
    return {
        "base_checklist": BASE_CHECKLIST,
        "surgery_types": list(SURGERY_RISK_MAP.keys()),
    }
