"""
Aetheris — SQLAlchemy Database Models
"""

from sqlalchemy import Column, String, Integer, Float, Boolean, DateTime, Text, ForeignKey, Enum
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from app.core.database import Base
import enum
import uuid


def gen_uuid():
    return str(uuid.uuid4())


# ── ENUMS ──────────────────────────────────────────────────────────────────
class SurgeryStatus(str, enum.Enum):
    SCHEDULED = "scheduled"
    PRE_OP    = "pre_op"
    IN_PROGRESS = "in_progress"
    RECOVERY  = "recovery"
    COMPLETE  = "complete"
    CANCELLED = "cancelled"

class AlertSeverity(str, enum.Enum):
    CRITICAL = "critical"
    WARNING  = "warning"
    INFO     = "info"

class ReportType(str, enum.Enum):
    OPERATIVE_NOTE    = "operative_note"
    DISCHARGE_SUMMARY = "discharge_summary"
    RISK_ASSESSMENT   = "risk_assessment"
    COMPLICATION_REPORT = "complication_report"

class ASAClass(str, enum.Enum):
    I   = "I"
    II  = "II"
    III = "III"
    IV  = "IV"
    V   = "V"


# ── PATIENT ────────────────────────────────────────────────────────────────
class Patient(Base):
    __tablename__ = "patients"

    id              = Column(String, primary_key=True, default=gen_uuid)
    name            = Column(String(200), nullable=False)
    age             = Column(Integer, nullable=False)
    gender          = Column(String(10), nullable=False)
    weight_kg       = Column(Float)
    height_cm       = Column(Float)
    blood_type      = Column(String(5))
    allergies       = Column(Text)          # JSON string list
    medications     = Column(Text)          # JSON string list
    medical_history = Column(Text)          # JSON string list
    asa_class       = Column(String(5))
    created_at      = Column(DateTime(timezone=True), server_default=func.now())
    updated_at      = Column(DateTime(timezone=True), onupdate=func.now())

    # Relationships
    surgeries   = relationship("Surgery",   back_populates="patient")
    vitals_logs = relationship("VitalsLog", back_populates="patient")
    alerts      = relationship("Alert",     back_populates="patient")
    reports     = relationship("Report",    back_populates="patient")


# ── SURGERY ────────────────────────────────────────────────────────────────
class Surgery(Base):
    __tablename__ = "surgeries"

    id              = Column(String, primary_key=True, default=gen_uuid)
    patient_id      = Column(String, ForeignKey("patients.id"), nullable=False)
    surgery_type    = Column(String(100), nullable=False)
    surgeon_name    = Column(String(200))
    anesthesiologist = Column(String(200))
    or_room         = Column(String(20))
    status          = Column(String(20), default=SurgeryStatus.SCHEDULED)
    scheduled_at    = Column(DateTime(timezone=True))
    started_at      = Column(DateTime(timezone=True))
    ended_at        = Column(DateTime(timezone=True))
    current_step    = Column(Integer, default=0)
    notes           = Column(Text)
    estimated_blood_loss_ml = Column(Float)
    duration_minutes = Column(Integer)
    created_at      = Column(DateTime(timezone=True), server_default=func.now())

    patient  = relationship("Patient", back_populates="surgeries")
    reports  = relationship("Report",  back_populates="surgery")


# ── VITALS LOG ──────────────────────────────────────────────────────────────
class VitalsLog(Base):
    __tablename__ = "vitals_logs"

    id           = Column(String, primary_key=True, default=gen_uuid)
    patient_id   = Column(String, ForeignKey("patients.id"), nullable=False)
    surgery_id   = Column(String, ForeignKey("surgeries.id"), nullable=True)
    heart_rate   = Column(Float)
    spo2         = Column(Float)
    systolic_bp  = Column(Float)
    diastolic_bp = Column(Float)
    temperature  = Column(Float)
    etco2        = Column(Float)
    resp_rate    = Column(Float)
    recorded_at  = Column(DateTime(timezone=True), server_default=func.now())

    patient = relationship("Patient", back_populates="vitals_logs")


# ── ALERT ──────────────────────────────────────────────────────────────────
class Alert(Base):
    __tablename__ = "alerts"

    id             = Column(String, primary_key=True, default=gen_uuid)
    patient_id     = Column(String, ForeignKey("patients.id"))
    surgery_id     = Column(String, ForeignKey("surgeries.id"), nullable=True)
    severity       = Column(String(20), default=AlertSeverity.WARNING)
    title          = Column(String(200), nullable=False)
    message        = Column(Text, nullable=False)
    vital_type     = Column(String(50))     # hr, spo2, bp, temp, etco2
    vital_value    = Column(Float)
    acknowledged   = Column(Boolean, default=False)
    acknowledged_by = Column(String(200))
    created_at     = Column(DateTime(timezone=True), server_default=func.now())

    patient = relationship("Patient", back_populates="alerts")


# ── RISK ASSESSMENT ────────────────────────────────────────────────────────
class RiskAssessment(Base):
    __tablename__ = "risk_assessments"

    id                 = Column(String, primary_key=True, default=gen_uuid)
    patient_id         = Column(String, ForeignKey("patients.id"))
    surgery_id         = Column(String, ForeignKey("surgeries.id"), nullable=True)
    overall_risk_score = Column(Float)
    cardiac_risk       = Column(Float)
    anesthesia_risk    = Column(Float)
    surgical_risk      = Column(Float)
    asa_predicted      = Column(String(5))
    drug_interactions  = Column(Text)   # JSON
    checklist_items    = Column(Text)   # JSON
    recommendation     = Column(Text)
    created_at         = Column(DateTime(timezone=True), server_default=func.now())


# ── REPORT ────────────────────────────────────────────────────────────────
class Report(Base):
    __tablename__ = "reports"

    id           = Column(String, primary_key=True, default=gen_uuid)
    patient_id   = Column(String, ForeignKey("patients.id"))
    surgery_id   = Column(String, ForeignKey("surgeries.id"), nullable=True)
    report_type  = Column(String(50), default=ReportType.OPERATIVE_NOTE)
    title        = Column(String(300))
    content      = Column(Text, nullable=False)
    status       = Column(String(30), default="draft")  # draft, sent_to_ehr, archived
    generated_by = Column(String(50), default="ai")     # ai, manual
    created_at   = Column(DateTime(timezone=True), server_default=func.now())

    patient = relationship("Patient", back_populates="reports")
    surgery = relationship("Surgery", back_populates="reports")
