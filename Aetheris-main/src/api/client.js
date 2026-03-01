const BASE_URL = import.meta.env?.VITE_API_URL || 'https://aetheris-backend.onrender.com';

async function apiRequest(endpoint, options = {}) {
    const response = await fetch(`${BASE_URL}${endpoint}`, {
        ...options,
        headers: {
            'Content-Type': 'application/json',
            ...(options.headers || {}),
        },
    });

    const data = await response.json().catch(() => null);

    if (!response.ok) {
        let errorMessage = `HTTP error ${response.status}`;
        if (data) {
            errorMessage = data.detail || data.message || errorMessage;
            // Handle FastAPI validation errors
            if (Array.isArray(errorMessage)) {
                errorMessage = errorMessage.map(e => `${e.loc.join('.')}: ${e.msg}`).join(', ');
            }
        }
        throw new Error(errorMessage);
    }

    return data;
}

// ── PATIENTS ─────────────────────────────────────────────────────────────────
export const getPatients = (status) =>
    apiRequest(`/api/patients/?${status ? `status=${status}` : ''}`);

export const getPatient = (id) =>
    apiRequest(`/api/patients/${id}`);

export const createPatient = (data) =>
    apiRequest('/api/patients/', { method: 'POST', body: JSON.stringify(data) });

export const dischargePatient = (id) =>
    apiRequest(`/api/patients/${id}/discharge`, { method: 'PATCH' });

// ── PRE-OP ────────────────────────────────────────────────────────────────────
export const runPreOpAssessment = (data) =>
    apiRequest('/api/preop/assess', { method: 'POST', body: JSON.stringify(data) });

async function apiUploadRequest(endpoint, formData) {
    const response = await fetch(`${BASE_URL}${endpoint}`, {
        method: 'POST',
        body: formData,
        // Browser automatically sets Content-Type to multipart/form-data with boundary
    });

    if (!response.ok) {
        let errorMessage = `HTTP error ${response.status}`;
        try {
            const errorData = await response.json();
            errorMessage = errorData.detail || errorData.message || errorMessage;
        } catch { }
        throw new Error(errorMessage);
    }

    return response.json();
}

// ── INTRA-OP ──────────────────────────────────────────────────────────────────
export const checkAnomalies = (data) =>
    apiRequest('/api/intraop/anomaly-check', { method: 'POST', body: JSON.stringify(data) });

export const sendVoiceCommand = (data) =>
    apiRequest('/api/intraop/voice-command', { method: 'POST', body: JSON.stringify(data) });

export const sendVoiceAudio = (patientId, audioBlob) => {
    const formData = new FormData();
    formData.append('patient_id', patientId);
    formData.append('audio_file', audioBlob, 'voice_command.webm');
    return apiUploadRequest('/api/intraop/voice-command-audio', formData);
};

export const sendTextCommand = (patientId, textQuery) =>
    apiRequest('/api/intraop/text-command', { method: 'POST', body: JSON.stringify({ patient_id: patientId, text_query: textQuery }) });

export const advanceProcedureStep = (data) =>
    apiRequest('/api/intraop/procedure-step', { method: 'PATCH', body: JSON.stringify(data) });

// ── POST-OP ───────────────────────────────────────────────────────────────────
export const getComplicationRisk = (data) =>
    apiRequest('/api/postop/complication-risk', { method: 'POST', body: JSON.stringify(data) });

// ── REPORTS ───────────────────────────────────────────────────────────────────
export const generateReport = (data) =>
    apiRequest('/api/reports/generate', { method: 'POST', body: JSON.stringify(data) });

export const sendToEHR = (data) =>
    apiRequest('/api/reports/send-to-ehr', { method: 'POST', body: JSON.stringify(data) });

// ── ALERTS ────────────────────────────────────────────────────────────────────
export const getAlerts = (params = {}) =>
    apiRequest(`/api/alerts/?${new URLSearchParams(params).toString()}`);

export const createAlert = (data) =>
    apiRequest('/api/alerts/', { method: 'POST', body: JSON.stringify(data) });

export const acknowledgeAlert = (id, data) =>
    apiRequest(`/api/alerts/${id}/acknowledge`, { method: 'PATCH', body: JSON.stringify(data) });

// ── HEALTH CHECK ──────────────────────────────────────────────────────────────
export const checkHealth = () =>
    apiRequest('/health');
