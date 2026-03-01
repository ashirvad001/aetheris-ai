"""Aetheris — Patients Routes"""
from fastapi import APIRouter, HTTPException
from app.schemas import PatientCreate, PatientResponse
from datetime import datetime
import uuid

router = APIRouter()

# In-memory store for demo (replace with DB in production)
_patients = {
    "p001": {"id":"p001","name":"Rajesh Kumar","age":58,"gender":"Male","weight_kg":82,"height_cm":172,
             "blood_type":"B+","allergies":["Penicillin"],"medications":["Warfarin","Aspirin","Metformin"],
             "medical_history":["Type 2 Diabetes","Hypertension","Atrial Fibrillation"],
             "asa_class":"III","status":"in_progress","created_at": datetime.utcnow().isoformat()},
    "p002": {"id":"p002","name":"Priya Sharma","age":42,"gender":"Female","weight_kg":65,"height_cm":162,
             "blood_type":"O+","allergies":[],"medications":["Metoprolol","Lisinopril"],
             "medical_history":["Hypertension"],"asa_class":"II","status":"pre_op",
             "created_at": datetime.utcnow().isoformat()},
    "p003": {"id":"p003","name":"Amit Patel","age":67,"gender":"Male","weight_kg":90,"height_cm":175,
             "blood_type":"A+","allergies":["Sulfa"],"medications":["Atorvastatin","Clopidogrel","Aspirin"],
             "medical_history":["CAD","Hypertension","Dyslipidemia"],
             "asa_class":"IV","status":"recovery","created_at": datetime.utcnow().isoformat()},
}

@router.get("/", summary="List all patients")
async def list_patients():
    return {"patients": list(_patients.values()), "total": len(_patients)}

@router.get("/{patient_id}", summary="Get patient by ID")
async def get_patient(patient_id: str):
    if patient_id not in _patients:
        raise HTTPException(status_code=404, detail="Patient not found")
    return _patients[patient_id]

@router.post("/", summary="Create new patient")
async def create_patient(req: PatientCreate):
    pid = str(uuid.uuid4())[:8]
    patient = {"id": pid, **req.dict(), "created_at": datetime.utcnow().isoformat()}
    _patients[pid] = patient
    return patient

@router.patch("/{patient_id}/discharge", summary="Discharge patient")
async def discharge_patient(patient_id: str):
    if patient_id not in _patients:
        raise HTTPException(status_code=404, detail="Patient not found")
    
    # Remove from active monitoring mock store
    discharged_patient = _patients.pop(patient_id)
    return {"status": "success", "message": f"Patient {discharged_patient.get('name', patient_id)} discharged successfully."}
