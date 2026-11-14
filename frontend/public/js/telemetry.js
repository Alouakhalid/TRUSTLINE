/**
 * Real-Time Telemetry Stream Manager.
 * Connects to /ws/telemetry with sequence validation, gap detection, and REST fallback.
 */

class TelemetryStream {
  constructor() {
    this.ws = null;
    this.isConnected = false;
    this.listeners = new Set();
    this.lastSequences = new Map();
    this.latestPackets = new Map();
    this.heartbeatInterval = null;
    this.pollInterval = null;
    this.reconnectAttempts = 0;
  }

  subscribe(callback) {
    this.listeners.add(callback);
    return () => this.listeners.delete(callback);
  }

  notify(packet) {
    this.latestPackets.set(packet.sensor_type, packet);
    for (const cb of this.listeners) {
      try { cb(packet); } catch (e) { console.error('Listener error:', e); }
    }
  }

  connect() {
    if (this.ws && (this.ws.readyState === WebSocket.OPEN || this.ws.readyState === WebSocket.CONNECTING)) {
      return;
    }

    const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
    const host = window.location.host || 'localhost:8000';
    const tokenParam = window.api.token ? `?token=${encodeURIComponent(window.api.token)}` : '';
    const demoParam = window.api.isDemo ? `${tokenParam ? '&' : '?'}demo=true` : '';
    const url = `${protocol}//${host}/ws/telemetry${tokenParam}${demoParam}`;

    console.log('[TelemetryStream] Connecting WebSocket:', url);
    try {
      this.ws = new WebSocket(url);
    } catch (err) {
      console.warn('[TelemetryStream] WebSocket constructor failed, starting REST fallback:', err);
      this.startRestFallback();
      return;
    }

    this.ws.onopen = () => {
      console.log('[TelemetryStream] WebSocket connected.');
      this.isConnected = true;
      this.reconnectAttempts = 0;
      this.stopRestFallback();
      this.startHeartbeat();
      window.dispatchEvent(new CustomEvent('telemetry-status', { detail: { connected: true, protocol: 'WEBSOCKET' } }));
    };

    this.ws.onmessage = (event) => {
      try {
        const data = JSON.parse(event.data);
        if (data.type === 'telemetry_packet' && data.packet) {
          const pkt = data.packet;
          this.validateSequence(pkt);
          this.notify(pkt);
        }
      } catch (e) {
        console.error('[TelemetryStream] Failed to parse frame:', e);
      }
    };

    this.ws.onclose = () => {
      console.warn('[TelemetryStream] WebSocket closed.');
      this.isConnected = false;
      this.stopHeartbeat();
      window.dispatchEvent(new CustomEvent('telemetry-status', { detail: { connected: false, protocol: 'OFFLINE' } }));
      this.scheduleReconnect();
    };

    this.ws.onerror = (err) => {
      console.warn('[TelemetryStream] WebSocket error:', err);
      this.ws.close();
    };
  }

  validateSequence(pkt) {
    const prev = this.lastSequences.get(pkt.sensor_type);
    if (prev !== undefined) {
      if (pkt.sequence_number === prev) {
        pkt._duplicate = true;
      } else if (pkt.sequence_number > prev + 1) {
        pkt._gap_detected = pkt.sequence_number - prev - 1;
      }
    }
    this.lastSequences.set(pkt.sensor_type, pkt.sequence_number);
  }

  startHeartbeat() {
    this.stopHeartbeat();
    this.heartbeatInterval = setInterval(() => {
      if (this.ws && this.ws.readyState === WebSocket.OPEN) {
        this.ws.send(JSON.stringify({ type: 'ping', timestamp: Date.now() }));
      }
    }, 15000);
  }

  stopHeartbeat() {
    if (this.heartbeatInterval) clearInterval(this.heartbeatInterval);
  }

  scheduleReconnect() {
    this.reconnectAttempts++;
    const delay = Math.min(10000, 1000 * Math.pow(1.5, this.reconnectAttempts));
    setTimeout(() => {
      if (!this.isConnected) {
        this.connect();
      }
    }, delay);

    // Fall back to REST polling while waiting for reconnection
    this.startRestFallback();
  }

  startRestFallback() {
    if (this.pollInterval) return;
    console.log('[TelemetryStream] Starting REST polling fallback (1000ms)...');
    window.dispatchEvent(new CustomEvent('telemetry-status', { detail: { connected: true, protocol: 'REST_POLLING' } }));
    
    const sensors = ['ECG', 'HR', 'SPO2', 'RESPIRATION', 'EDA', 'SKIN_TEMP', 'CORE_TEMP', 'ACCELEROMETER'];
    this.pollInterval = setInterval(async () => {
      for (const s of sensors) {
        try {
          const res = await window.api.getLatestTelemetry(s, window.api.astronautId);
          if (res && res.packet) {
            this.validateSequence(res.packet);
            this.notify(res.packet);
          }
        } catch (e) {
          // Ignore transient poll error
        }
      }
    }, 1200);
  }

  stopRestFallback() {
    if (this.pollInterval) {
      clearInterval(this.pollInterval);
      this.pollInterval = null;
    }
  }
}

window.telemetryStream = new TelemetryStream();
