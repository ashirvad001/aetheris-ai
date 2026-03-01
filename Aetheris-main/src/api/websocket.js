const WS_BASE_URL =
    import.meta.env?.VITE_WS_URL ||
    (import.meta.env?.VITE_API_URL || 'https://aetheris-backend.onrender.com').replace(/^http/, 'ws');

const RECONNECT_DELAY_MS = 3000;

export class VitalsWebSocket {
    /**
     * @param {string|number} patientId
     * @param {(vitals: object) => void} onVitals   – called for normal vitals frames
     * @param {(alerts: object[]) => void} onAlert  – called when an ANOMALY_ALERT arrives
     * @param {(error: Event) => void} [onError]    – optional error handler
     */
    constructor(patientId, onVitals, onAlert, onError) {
        this.patientId = patientId;
        this.onVitals = onVitals;
        this.onAlert = onAlert;
        this.onError = onError || (() => { });

        this._ws = null;
        this._reconnectTimer = null;
        this._manualClose = false;
    }

    connect() {
        this._manualClose = false;
        this._openSocket();
    }

    disconnect() {
        this._manualClose = true;
        clearTimeout(this._reconnectTimer);
        if (this._ws) {
            this._ws.close();
            this._ws = null;
        }
    }

    // ── private ────────────────────────────────────────────────────────────────

    _openSocket() {
        const url = `${WS_BASE_URL}/api/intraop/vitals-stream/${this.patientId}`;
        const ws = new WebSocket(url);
        this._ws = ws;

        ws.onmessage = (event) => {
            let data;
            try {
                data = JSON.parse(event.data);
            } catch {
                console.warn('[VitalsWebSocket] Could not parse message:', event.data);
                return;
            }

            if (data.type === 'ANOMALY_ALERT') {
                this.onAlert(data.alerts);
            } else {
                this.onVitals(data);
            }
        };

        ws.onerror = (event) => {
            if (!this._manualClose) {
                this.onError(event);
            }
        };

        ws.onclose = () => {
            if (!this._manualClose) {
                this._scheduleReconnect();
            }
        };
    }

    _scheduleReconnect() {
        this._reconnectTimer = setTimeout(() => {
            console.info(
                `[VitalsWebSocket] Reconnecting for patient ${this.patientId}…`
            );
            this._openSocket();
        }, RECONNECT_DELAY_MS);
    }
}
