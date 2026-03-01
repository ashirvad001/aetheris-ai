"""
Aetheris — Pydantic Schemas (Request & Response Models)
"""

from pydantic import BaseModel, Field, validator
from typing import Optional, List, Dict, Any
from datetime import datetime
from enum import Enum


# ── ENUMS ──────────────────────────────────────────────────────────────────
class ASAClass(str, Enum):
    I = "I"; II = "II"; III = "III"; IV = "IV"; V = "V"

class SurgeryType(str, Enum):
    CARDIAC      = "Cardiac"
    ORTHOPEDIC   = "Orthopedic"
    NEUROLOGICAL = "Neurological"
    GENERAL      = "General"
    VASCULAR     = "Vascular"
    THORACIC     = "Thoracic"
    ABDOMINAL    = "Abdominal"
    OPHTHALMIC   = "Ophthalmic"

class AlertSeverity(str, Enum):
    CRITICAL = "critical"
    WARNING  = "warning"
    INFO     = "info"

class ReportType(str, Enum):
    OPERATIVE_NOTE      = "operative_note"
    DISCHARGE_SUMMARY   = "discharge_summary"
    RISK_ASSESSMENT     = "risk_assessment"
    COMPLICATION_REPORT = "complication_report"


# ── PATIENT SCHEMAS ────────────────────────────────────────────────────────
class PatientCreate(BaseModel):
    name:            str        = Field(..., min_length=2, max_length=200)
    age:             int        = Field(..., ge=0, le=120)
    gender:          str        = Field(..., pattern="^(Male|Female|Other)$")
    weight_kg:       Optional[float] = Field(None, ge=1, le=300)
    height_cm:       Optional[float] = Field(None, ge=30, le=250)
    blood_type:      Optional[str]   = None
    allergies:       List[str]       = []
    medications:     List[str]       = []
    medical_history: List[str]       = []
    asa_class:       Optional[ASAClass] = None

class PatientResponse(PatientCreate):
    id:         str
    created_at: datetime
    class Config: from_attributes = True


# ── PRE-OP SCHEMAS ─────────────────────────────────────────────────────────
class PreOpAssessmentRequest(BaseModel):
    patient_id:    str
    surgery_type:  SurgeryType
    asa_class:     Optional[ASAClass] = None
    medications:   List[str] = []
    allergies:     List[str] = []
    medical_history: List[str] = []
    # Additional clinical fields
    weight_kg:     Optional[float] = None
    height_cm:     Optional[float] = None
    systolic_bp:   Optional[float] = Field(None, ge=60, le=250)
    diastolic_bp:  Optional[float] = Field(None, ge=40, le=150)
    heart_rate:    Optional[float] = Field(None, ge=30, le=200)
    spo2:          Optional[float] = Field(None, ge=70, le=100)
    temperature:   Optional[float] = Field(None, ge=34.0, le=42.0)
    diabetes:      bool = False
    hypertension:  bool = False
    cardiac_hx:    bool = False
    smoking:       bool = False

class DrugInteraction(BaseModel):
    drug_a:      str
    drug_b:      str
    severity:    str  # "HIGH", "MEDIUM", "LOW"
    description: str
    source:      str = "OpenFDA"

class RiskBreakdown(BaseModel):
    cardiac_risk:     float = Field(..., ge=0, le=100)
    anesthesia_risk:  float = Field(..., ge=0, le=100)
    surgical_risk:    float = Field(..., ge=0, le=100)

class ChecklistItem(BaseModel):
    id:          int
    label:       str
    checked:     bool = False
    required:    bool = True
    category:    str  = "general"

class PreOpAssessmentResponse(BaseModel):
    assessment_id:      str
    patient_id:         str
    overall_risk_score: float
    risk_level:         str         # "LOW", "MEDIUM", "HIGH", "CRITICAL"
    risk_breakdown:     RiskBreakdown
    asa_predicted:      str
    drug_interactions:  List[DrugInteraction]
    checklist:          List[ChecklistItem]
    recommendation:     str
    ai_summary:         str
    created_at:         datetime


# ── VITALS SCHEMAS ─────────────────────────────────────────────────────────
class VitalsReading(BaseModel):
    heart_rate:   float = Field(..., ge=0, le=300,  description="BPM")
    spo2:         float = Field(..., ge=0, le=100,  description="% Oxygen saturation")
    systolic_bp:  float = Field(..., ge=0, le=300,  description="mmHg")
    diastolic_bp: float = Field(..., ge=0, le=200,  description="mmHg")
    temperature:  float = Field(..., ge=30, le=45,  description="Celsius")
    etco2:        float = Field(..., ge=0, le=100,  description="mmHg")
    resp_rate:    float = Field(..., ge=0, le=60,   description="Breaths/min")
    recorded_at:  Optional[datetime] = None

class VitalsLogRequest(BaseModel):
    patient_id: str
    surgery_id: Optional[str] = None
    vitals:     VitalsReading

class VitalsHistoryResponse(BaseModel):
    patient_id: str
    readings:   List[VitalsReading]
    latest:     Optional[VitalsReading]


# ── ALERT SCHEMAS ──────────────────────────────────────────────────────────
class AlertCreate(BaseModel):
    patient_id:  str
    surgery_id:  Optional[str] = None
    severity:    AlertSeverity
    title:       str
    message:     str
    vital_type:  Optional[str] = None
    vital_value: Optional[float] = None

class AlertResponse(AlertCreate):
    id:           str
    acknowledged: bool
    created_at:   datetime
    class Config: from_attributes = True

class AcknowledgeRequest(BaseModel):
    acknowledged_by: str = "clinical_staff"


# ── INTRA-OP SCHEMAS ───────────────────────────────────────────────────────
class AnomalyCheckRequest(BaseModel):
    patient_id: str
    surgery_id: Optional[str] = None
    vitals:     VitalsReading

class AnomalyResult(BaseModel):
    has_anomaly:   bool
    alerts_fired:  List[AlertCreate]
    vitals_status: Dict[str, str]   # {"hr": "normal", "spo2": "critical", ...}

class VoiceCommandRequest(BaseModel):
    patient_id:  str
    surgery_id:  Optional[str] = None
    audio_b64:   Optional[str] = None   # base64 encoded audio
    text_query:  Optional[str] = None   # fallback: text query directly

class VoiceCommandResponse(BaseModel):
    transcription: str
    response:      str
    vitals_cited:  Optional[Dict[str, Any]] = None

class ProcedureStepUpdate(BaseModel):
    surgery_id:   str
    current_step: int = Field(..., ge=0, le=10)
    note:         Optional[str] = None


# ── POST-OP SCHEMAS ────────────────────────────────────────────────────────
class ComplicationRiskRequest(BaseModel):
    patient_id:   str
    surgery_id:   Optional[str] = None
    surgery_type: SurgeryType
    duration_min: Optional[int]   = None
    blood_loss_ml: Optional[float] = None
    asa_class:    Optional[str]   = None
    age:          Optional[int]   = None
    weight_kg:    Optional[float] = None
    height_cm:    Optional[float] = None
    diabetes:     bool = False
    hypertension: bool = False
    cardiac_hx:   bool = False
    smoker:       bool = False

class ComplicationRisk(BaseModel):
    name:        str
    risk_pct:    float
    risk_level:  str   # LOW / MEDIUM / HIGH
    description: str

class ComplicationRiskResponse(BaseModel):
    patient_id:      str
    overall_score:   float
    risk_level:      str
    complications:   List[ComplicationRisk]
    recommendation:  str


# ── REPORT SCHEMAS ──────────────────────────────────────────────────────────
class ReportGenerateRequest(BaseModel):
    patient_id:   str
    surgery_id:   Optional[str] = None
    report_type:  ReportType = ReportType.OPERATIVE_NOTE
    extra_notes:  Optional[str] = None
    patient_name: Optional[str] = None
    patient_age:  Optional[str] = None
    surgery_name: Optional[str] = None

class ReportResponse(BaseModel):
    id:          str
    patient_id:  str
    surgery_id:  Optional[str]
    report_type: str
    title:       str
    content:     str
    status:      str
    created_at:  datetime
    class Config: from_attributes = True

class ReportSendToEHR(BaseModel):
    report_id:  str
    ehr_system: str = "mock_ehr"   # In production: Epic, Cerner, etc.


# ── SURGERY SCHEMAS ────────────────────────────────────────────────────────
class SurgeryCreate(BaseModel):
    patient_id:       str
    surgery_type:     SurgeryType
    surgeon_name:     Optional[str] = None
    anesthesiologist: Optional[str] = None
    or_room:          Optional[str] = None
    scheduled_at:     Optional[datetime] = None
    notes:            Optional[str] = None

class SurgeryResponse(SurgeryCreate):
    id:           str
    status:       str
    current_step: int
    started_at:   Optional[datetime]
    ended_at:     Optional[datetime]
    created_at:   datetime
    class Config: from_attributes = True
