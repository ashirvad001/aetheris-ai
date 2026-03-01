"""Aetheris — Post-Operative Routes"""
from fastapi import APIRouter, HTTPException
from app.schemas import ComplicationRiskRequest, ComplicationRiskResponse, ReportGenerateRequest
from app.services.postop_service import predict_complications, run_report_generation

router = APIRouter()

@router.post("/complication-risk", response_model=ComplicationRiskResponse,
             summary="Predict post-operative complication risks")
async def complication_risk(req: ComplicationRiskRequest):
    """ML-powered prediction for DVT, Infection, Pneumonia, and 30-day Readmission."""
    try:
        return predict_complications(req)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
