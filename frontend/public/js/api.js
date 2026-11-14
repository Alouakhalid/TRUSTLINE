/**
 * TRUSTLINE Unified REST & WebSocket API Client.
 * Connects to the local FastAPI backend (34+ operational endpoints).
 */

class TrustlineAPI {
  constructor(baseUrl = '') {
    this.baseUrl = baseUrl || window.location.origin;
    this.token = localStorage.getItem('trustline_token') || null;
    this.role = localStorage.getItem('trustline_role') || 'ASTRONAUT';
    this.username = localStorage.getItem('trustline_user') || 'astronaut_1';
    this.astronautId = localStorage.getItem('trustline_astroid') || 'AST-001';
    this.isDemo = localStorage.getItem('trustline_demo') === 'true';
  }

  setDemoMode(isDemo) {
    this.isDemo = Boolean(isDemo);
    localStorage.setItem('trustline_demo', this.isDemo ? 'true' : 'false');
  }

  setCredentials(token, user) {
    this.token = token;
    this.role = user.role;
    this.username = user.username;
    this.astronautId = user.astronaut_id || 'AST-001';
    localStorage.setItem('trustline_token', token);
    localStorage.setItem('trustline_role', this.role);
    localStorage.setItem('trustline_user', this.username);
    localStorage.setItem('trustline_astroid', this.astronautId);
  }

  logout() {
    this.token = null;
    localStorage.removeItem('trustline_token');
  }

  async request(endpoint, options = {}) {
    const url = `${this.baseUrl}${endpoint}`;
    const headers = {
      'Accept': 'application/json',
      ...(options.headers || {})
    };

    if (this.token) {
      headers['Authorization'] = `Bearer ${this.token}`;
    }

    if (this.isDemo) {
      headers['X-Trustline-Mode'] = 'demo';
    }

    if (!(options.body instanceof FormData) && options.body && typeof options.body === 'object') {
      headers['Content-Type'] = 'application/json';
      options.body = JSON.stringify(options.body);
    }

    const config = { ...options, headers };
    try {
      const response = await fetch(url, config);
      if (response.status === 401) {
        console.warn('Session expired or unauthorized.');
      }
      const data = await response.json().catch(() => ({}));
      if (!response.ok) {
        throw new Error(data.detail || `HTTP ${response.status}: ${response.statusText}`);
      }
      return data;
    } catch (err) {
      console.error(`API Error on ${endpoint}:`, err);
      throw err;
    }
  }

  // --- Auth & Users ---
  async register(username, password, role = 'ASTRONAUT', astronautId = null) {
    return this.request('/auth/register', {
      method: 'POST',
      body: { username, password, role, astronaut_id: astronautId }
    });
  }

  async login(username, password) {
    const res = await this.request('/auth/login', {
      method: 'POST',
      body: { username, password }
    });
    if (res.access_token) {
      const me = await this.getMe(res.access_token);
      this.setCredentials(res.access_token, me);
    }
    return res;
  }

  async getMe(overrideToken = null) {
    const headers = overrideToken ? { 'Authorization': `Bearer ${overrideToken}` } : {};
    return this.request('/auth/me', { headers });
  }

  async listUsers() {
    return this.request('/admin/users');
  }

  async listAuditLogs(action = null, limit = 50) {
    const params = new URLSearchParams({ limit });
    if (action) params.append('action', action);
    return this.request(`/admin/audit?${params}`);
  }

  // --- Chat Sessions ---
  async listSessions() {
    return this.request('/chat/sessions');
  }

  async createSession(title = 'Mission Discussion') {
    return this.request('/chat/sessions', {
      method: 'POST',
      body: { title }
    });
  }

  async patchSession(sessionId, title = null, status = null) {
    return this.request(`/chat/sessions/${sessionId}`, {
      method: 'PATCH',
      body: { title, status }
    });
  }

  async deleteSession(sessionId) {
    return this.request(`/chat/sessions/${sessionId}`, { method: 'DELETE' });
  }

  async getMessages(sessionId) {
    return this.request(`/chat/sessions/${sessionId}/messages`);
  }

  async sendMessage(sessionId, content) {
    return this.request(`/chat/sessions/${sessionId}/messages`, {
      method: 'POST',
      body: { content }
    });
  }

  // --- Agent Memory ---
  async listMemories(astronautId, namespace = null, status = null, longTerm = null) {
    const params = new URLSearchParams({ astronaut_id: astronautId });
    if (namespace) params.append('namespace', namespace);
    if (status) params.append('verification_status', status);
    if (longTerm !== null) params.append('long_term', String(longTerm));
    return this.request(`/memory?${params}`);
  }

  async createMemory(req) {
    return this.request('/memory', {
      method: 'POST',
      body: req
    });
  }

  async updateMemory(memoryId, req) {
    return this.request(`/memory/${memoryId}`, {
      method: 'PATCH',
      body: req
    });
  }

  async deleteMemory(memoryId) {
    return this.request(`/memory/${memoryId}`, { method: 'DELETE' });
  }

  // --- Telemetry & Sensors ---
  async getLatestTelemetry(sensorType, astronautId = 'AST-001') {
    return this.request(`/telemetry/latest?sensor_type=${sensorType}&astronaut_id=${astronautId}`);
  }

  async getTelemetryHistory(sensorType, astronautId = 'AST-001', limit = 100) {
    return this.request(`/telemetry/history?sensor_type=${sensorType}&astronaut_id=${astronautId}&limit=${limit}`);
  }

  async ingestTelemetryPacket(packet) {
    return this.request('/telemetry/ingest', {
      method: 'POST',
      body: packet
    });
  }

  // --- Space Radiation ---
  async getRadiationLimits() {
    return this.request('/radiation/limits');
  }

  async getLatestRadiation() {
    return this.request('/radiation/latest');
  }

  // --- Clinical Assessments & Supervisor ---
  async runAssessment(astronautId = 'AST-001', reason = 'Flight Surgeon Clinical Sweep', sessionId = null) {
    return this.request('/assessments', {
      method: 'POST',
      body: {
        astronaut_id: astronautId,
        reason,
        session_id: sessionId,
        mission_context: {
          flight_phase: 'DEEP_SPACE_TRANSIT',
          cabin_pressure_kpa: 101.3
        }
      }
    });
  }

  async listAssessments(astronautId = 'AST-001', limit = 10) {
    return this.request(`/assessments?astronaut_id=${astronautId}&limit=${limit}`);
  }

  // --- Medical Documents ---
  async uploadDocument(file, docType = 'LAB_REPORT', astronautId = 'AST-001') {
    const formData = new FormData();
    formData.append('file', file);
    formData.append('document_type', docType);
    formData.append('astronaut_id', astronautId);
    return this.request('/documents/upload', {
      method: 'POST',
      body: formData
    });
  }

  async listDocuments(astronautId = null, status = null) {
    const params = new URLSearchParams();
    if (astronautId) params.append('astronaut_id', astronautId);
    if (status) params.append('status', status);
    return this.request(`/documents?${params}`);
  }

  async verifyDocument(docId, action, reviewNotes = '', editedFindings = null) {
    return this.request(`/documents/${docId}/verify`, {
      method: 'POST',
      body: { action, review_notes: reviewNotes, edited_findings: editedFindings }
    });
  }

  // --- Connectivity & Offline Sync ---
  async getConnectivity() {
    return this.request('/connectivity');
  }

  async getSyncStatus() {
    return this.request('/sync/status');
  }

  async runSync(limit = 25) {
    return this.request('/admin/sync/run', {
      method: 'POST',
      body: { limit }
    });
  }

  async getTransitions(kind = null, limit = 50) {
    const params = new URLSearchParams({ limit });
    if (kind) params.append('kind', kind);
    return this.request(`/admin/transitions?${params}`);
  }
}

window.api = new TrustlineAPI();
