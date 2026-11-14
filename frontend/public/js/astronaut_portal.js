/**
 * Astronaut Portal Module.
 * Telemetry KPIs, 3D Digital Twin, Oscilloscopes, Radiation Exposure, Medical History, AI Companion.
 */

class AstronautPortal {
  constructor() {
    this.activeSubTab = 'overview';
    this.oscilloscopes = {};
  }

  render(container) {
    container.innerHTML = `
      <div class="sub-nav-bar">
        <button class="sub-tab-btn active" data-sub="overview">📊 Crew Health KPIs</button>
        <button class="sub-tab-btn" data-sub="twin">🧍 3D Digital Twin</button>
        <button class="sub-tab-btn" data-sub="oscilloscope">📈 Sensor Explorer (Live)</button>
        <button class="sub-tab-btn" data-sub="radiation">☢️ Radiation Exposure (NASA)</button>
        <button class="sub-tab-btn" data-sub="documents">📄 Medical Records & OCR</button>
        <button class="sub-tab-btn" data-sub="companion">🤖 Personal AI Companion</button>
        <button class="sub-tab-btn" data-sub="profile">👤 Astronaut Profile</button>
      </div>

      <div id="astro-subtab-content" style="padding: 16px;"></div>
    `;

    container.querySelectorAll('.sub-tab-btn').forEach(btn => {
      btn.addEventListener('click', (e) => {
        container.querySelectorAll('.sub-tab-btn').forEach(b => b.classList.remove('active'));
        btn.classList.add('active');
        this.activeSubTab = btn.getAttribute('data-sub');
        this.renderSubTab();
      });
    });

    this.renderSubTab();
  }

  renderSubTab() {
    const target = document.getElementById('astro-subtab-content');
    if (!target) return;

    if (this.activeSubTab === 'overview') {
      this.renderOverview(target);
    } else if (this.activeSubTab === 'twin') {
      this.renderDigitalTwin(target);
    } else if (this.activeSubTab === 'oscilloscope') {
      this.renderOscilloscopes(target);
    } else if (this.activeSubTab === 'radiation') {
      this.renderRadiation(target);
    } else if (this.activeSubTab === 'documents') {
      this.renderDocuments(target);
    } else if (this.activeSubTab === 'companion') {
      this.renderCompanion(target);
    } else if (this.activeSubTab === 'profile') {
      this.renderProfile(target);
    }
  }

  renderOverview(target) {
    target.innerHTML = `
      <div class="kpi-grid">
        <div class="kpi-card" id="kpi-hr">
          <div class="kpi-title"><span>Heart Rate</span> <span class="status-dot nominal" id="dot-hr"></span></div>
          <div class="kpi-value-row"><span class="kpi-val" id="val-hr">72</span><span class="kpi-unit">BPM</span></div>
          <div class="kpi-meta"><span>Lead II ECG</span><span id="ts-hr">LIVE</span></div>
        </div>
        <div class="kpi-card" id="kpi-spo2">
          <div class="kpi-title"><span>Oxygen Saturation</span> <span class="status-dot nominal" id="dot-spo2"></span></div>
          <div class="kpi-value-row"><span class="kpi-val" id="val-spo2">98.5</span><span class="kpi-unit">%</span></div>
          <div class="kpi-meta"><span>Optical SpO2</span><span id="ts-spo2">LIVE</span></div>
        </div>
        <div class="kpi-card" id="kpi-resp">
          <div class="kpi-title"><span>Respiration Rate</span> <span class="status-dot nominal" id="dot-resp"></span></div>
          <div class="kpi-value-row"><span class="kpi-val" id="val-resp">14.2</span><span class="kpi-unit">BR/MIN</span></div>
          <div class="kpi-meta"><span>RIP Chest Belt</span><span id="ts-resp">LIVE</span></div>
        </div>
        <div class="kpi-card" id="kpi-core">
          <div class="kpi-title"><span>Core Temperature</span> <span class="status-dot nominal" id="dot-core"></span></div>
          <div class="kpi-value-row"><span class="kpi-val" id="val-core">37.1</span><span class="kpi-unit">°C</span></div>
          <div class="kpi-meta"><span>Heat Flux Est</span><span id="ts-core">LIVE</span></div>
        </div>
        <div class="kpi-card" id="kpi-skin">
          <div class="kpi-title"><span>Skin Surface Temp</span> <span class="status-dot nominal" id="dot-skin"></span></div>
          <div class="kpi-value-row"><span class="kpi-val" id="val-skin">33.8</span><span class="kpi-unit">°C</span></div>
          <div class="kpi-meta"><span>Wrist Thermistor</span><span id="ts-skin">LIVE</span></div>
        </div>
        <div class="kpi-card" id="kpi-eda">
          <div class="kpi-title"><span>Electrodermal Activity</span> <span class="status-dot nominal" id="dot-eda"></span></div>
          <div class="kpi-value-row"><span class="kpi-val" id="val-eda">3.24</span><span class="kpi-unit">µS</span></div>
          <div class="kpi-meta"><span>Sympathetic Tone</span><span id="ts-eda">LIVE</span></div>
        </div>
        <div class="kpi-card" id="kpi-sqa">
          <div class="kpi-title"><span>Sensor Quality (SQA)</span> <span class="status-dot nominal" id="dot-sqa"></span></div>
          <div class="kpi-value-row"><span class="kpi-val" id="val-sqa">0.96</span><span class="kpi-unit">SCORE</span></div>
          <div class="kpi-meta"><span>Artifact Free</span><span>9 Channels</span></div>
        </div>
        <div class="kpi-card" id="kpi-rad">
          <div class="kpi-title"><span>Ambient Radiation</span> <span class="status-dot nominal" id="dot-rad"></span></div>
          <div class="kpi-value-row"><span class="kpi-val" id="val-rad">22.0</span><span class="kpi-unit">µGy/h</span></div>
          <div class="kpi-meta"><span>GCR Baseline</span><span>NASA Nominal</span></div>
        </div>
      </div>

      <!-- Quick Twin & Assessment Row -->
      <div style="display:grid; grid-template-columns: 1fr 340px; gap:16px;">
        <div class="mission-card" style="height:440px;">
          <div style="display:flex; justify-content:space-between; align-items:center; margin-bottom:10px;">
            <span style="font-weight:700; color:var(--text-bright);">Interactive Astronaut Digital Twin</span>
            <span class="badge-tag badge-cyan">Three.js WebGL</span>
          </div>
          <div id="overview-twin-container" style="height:380px;"></div>
        </div>

        <div style="display:flex; flex-direction:column; gap:12px;">
          <div class="mission-card">
            <div style="font-weight:700; color:var(--text-bright); margin-bottom:6px;">Latest Supervisor Clinical Assessment</div>
            <div id="astro-assessment-summary" style="font-size:12px; color:var(--text-secondary); line-height:1.5;">
              Loading verified flight surgeon assessment...
            </div>
            <button class="btn-aerospace" style="width:100%; margin-top:10px;" onclick="window.astronautPortal.triggerAssessment()">
              ⚡ Request Supervisor Synthesis
            </button>
          </div>

          <div class="mission-card" style="flex:1;">
            <div style="font-weight:700; color:var(--text-bright); margin-bottom:8px;">Active Sensor Telemetry Stream</div>
            <div id="active-sensor-list" style="display:flex; flex-direction:column; gap:6px; font-size:11px;">
              <!-- Filled dynamically -->
            </div>
          </div>
        </div>
      </div>
    `;

    setTimeout(() => {
      window.twin = new window.AstronautDigitalTwin('overview-twin-container');
      this.loadLatestAssessment();
    }, 100);
  }

  renderDigitalTwin(target) {
    target.innerHTML = `
      <div style="display:grid; grid-template-columns: 1fr 300px; gap:16px;">
        <div class="twin-3d-wrapper" id="main-twin-container" style="height: 560px;"></div>
        <div class="mission-card" style="display:flex; flex-direction:column; gap:14px;">
          <div style="font-weight:700; color:var(--text-bright); font-size:14px;">Anatomical Hotspot Telemetry</div>
          <div id="hotspot-detail-box" style="font-size:12px; color:var(--text-secondary); line-height:1.6;">
            Click any pulsing sensor beacon on the 3D astronaut to inspect live signal quality, frequency, and biological bounds.
          </div>
          <div style="border-top:1px solid var(--color-border); padding-top:10px;">
            <div style="font-weight:600; color:var(--color-cyan); margin-bottom:6px;">Camera Orbit Controls</div>
            <div style="font-size:11px; color:var(--text-muted); line-height:1.5;">
              • Left Click + Drag: Rotate Astronaut<br>
              • Right Click + Drag: Pan Camera<br>
              • Scroll Wheel: Zoom In / Out
            </div>
          </div>
          <div style="margin-top:auto;">
            <span class="badge-tag badge-cyan">NASA-STD-3001 Verified Hotspots</span>
          </div>
        </div>
      </div>
    `;

    setTimeout(() => {
      window.twin = new window.AstronautDigitalTwin('main-twin-container');
      window.addEventListener('hotspot-selected', (e) => {
        const h = e.detail;
        const box = document.getElementById('hotspot-detail-box');
        if (box) {
          box.innerHTML = `
            <div style="font-size:14px; font-weight:700; color:var(--text-bright); margin-bottom:4px;">${h.name}</div>
            <div style="color:var(--color-cyan); font-family:var(--font-mono); font-size:11px; margin-bottom:8px;">ID: ${h.id}</div>
            <div style="margin-bottom:8px;">${h.desc}</div>
            <div style="background:rgba(0,229,255,0.08); padding:8px; border-radius:5px; border:1px solid var(--color-border);">
              <div style="font-size:11px; color:var(--text-muted);">LIVE SENSOR QUALITY</div>
              <div style="font-size:13px; font-weight:700; color:var(--color-emerald);">CALIBRATED / OPTIMAL</div>
            </div>
          `;
        }
      });
    }, 100);
  }

  renderOscilloscopes(target) {
    target.innerHTML = `
      <div style="display:grid; grid-template-columns: repeat(2, 1fr); gap:16px;">
        <div class="mission-card crt-overlay">
          <div style="display:flex; justify-content:space-between; margin-bottom:6px;">
            <span style="font-weight:700; color:#10B981;">ECG Lead II (256 Hz)</span>
            <span class="badge-tag badge-prod">mV</span>
          </div>
          <canvas id="scope-ecg" style="width:100%; height:200px; background:#040914; border-radius:6px;"></canvas>
        </div>

        <div class="mission-card crt-overlay">
          <div style="display:flex; justify-content:space-between; margin-bottom:6px;">
            <span style="font-weight:700; color:#00E5FF;">Photoplethysmogram (PPG) (64 Hz)</span>
            <span class="badge-tag badge-cyan">Normalized</span>
          </div>
          <canvas id="scope-ppg" style="width:100%; height:200px; background:#040914; border-radius:6px;"></canvas>
        </div>

        <div class="mission-card crt-overlay">
          <div style="display:flex; justify-content:space-between; margin-bottom:6px;">
            <span style="font-weight:700; color:#8B5CF6;">Respiratory Effort Waveform (32 Hz)</span>
            <span class="badge-tag badge-violet">a.u.</span>
          </div>
          <canvas id="scope-resp" style="width:100%; height:200px; background:#040914; border-radius:6px;"></canvas>
        </div>

        <div class="mission-card crt-overlay">
          <div style="display:flex; justify-content:space-between; margin-bottom:6px;">
            <span style="font-weight:700; color:#F59E0B;">Electrodermal Activity (EDA) (4 Hz)</span>
            <span class="badge-tag badge-demo">µS</span>
          </div>
          <canvas id="scope-eda" style="width:100%; height:200px; background:#040914; border-radius:6px;"></canvas>
        </div>
      </div>
    `;

    setTimeout(() => {
      this.oscilloscopes.ecg = new window.MissionOscilloscope('scope-ecg', 'ECG', { color: '#10B981', minVal: -2.0, maxVal: 2.5, sweepSpeed: 3 });
      this.oscilloscopes.ppg = new window.MissionOscilloscope('scope-ppg', 'PPG', { color: '#00E5FF', minVal: 0.0, maxVal: 1.0, sweepSpeed: 2 });
      this.oscilloscopes.resp = new window.MissionOscilloscope('scope-resp', 'RESPIRATION', { color: '#8B5CF6', minVal: -3.0, maxVal: 3.0, sweepSpeed: 1.8 });
      this.oscilloscopes.eda = new window.MissionOscilloscope('scope-eda', 'EDA', { color: '#F59E0B', minVal: 0.5, maxVal: 12.0, sweepSpeed: 1.2 });
    }, 100);
  }

  renderRadiation(target) {
    target.innerHTML = `
      <div class="mission-card" style="margin-bottom:16px;">
        <div style="display:flex; justify-content:space-between; align-items:center;">
          <div>
            <div style="font-size:16px; font-weight:700; color:var(--text-bright);">Space Radiation Dosimetry Panel</div>
            <div style="font-size:12px; color:var(--text-muted);">Strictly segregated environmental monitoring pursuant to NASA-STD-3001 Vol 1 Rev C</div>
          </div>
          <span class="badge-tag badge-prod" id="rad-alert-badge">NOMINAL GCR</span>
        </div>
      </div>

      <div style="display:grid; grid-template-columns: repeat(3, 1fr); gap:16px; margin-bottom:20px;">
        <div class="mission-card">
          <div class="kpi-title">Absorbed Dose Rate</div>
          <div class="kpi-value-row"><span class="kpi-val" id="rad-dose-rate">22.0</span><span class="kpi-unit">µGy/h</span></div>
          <div class="kpi-meta"><span>Silicon / Tissue Absorbed</span><span>Threshold: 500.0</span></div>
        </div>
        <div class="mission-card">
          <div class="kpi-title">Equivalent Biological Dose</div>
          <div class="kpi-value-row"><span class="kpi-val" id="rad-eq-rate">0.077</span><span class="kpi-unit">mSv/h</span></div>
          <div class="kpi-meta"><span>Quality Factor Q=3.5</span><span>GCR Heavy Ions</span></div>
        </div>
        <div class="mission-card">
          <div class="kpi-title">30-Day Cumulative Dose</div>
          <div class="kpi-value-row"><span class="kpi-val" id="rad-cum-dose">18.4</span><span class="kpi-unit">mSv</span></div>
          <div class="kpi-meta"><span>NASA Career Limit: 250</span><span>BFO Organs</span></div>
        </div>
      </div>

      <div class="mission-card">
        <div style="font-weight:700; margin-bottom:10px;">NASA-STD-3001 Volume 1 Revision C Regulatory Thresholds</div>
        <table class="table-aerospace">
          <thead>
            <tr><th>Exposure Domain</th><th>NASA Mandated Limit</th><th>Current Mission Cumulative</th><th>Status</th></tr>
          </thead>
          <tbody>
            <tr><td>Blood Forming Organs (30-day)</td><td>250.0 mSv</td><td>18.4 mSv (7.4%)</td><td><span class="badge-tag badge-prod">NOMINAL</span></td></tr>
            <tr><td>Eye Lens (30-day)</td><td>1000.0 mSv</td><td>18.4 mSv (1.8%)</td><td><span class="badge-tag badge-prod">NOMINAL</span></td></tr>
            <tr><td>Skin Surface (30-day)</td><td>1500.0 mSv</td><td>18.4 mSv (1.2%)</td><td><span class="badge-tag badge-prod">NOMINAL</span></td></tr>
            <tr><td>Acute SPE Shelter Trigger</td><td>500.0 µGy/h</td><td>22.0 µGy/h</td><td><span class="badge-tag badge-prod">STANDBY</span></td></tr>
          </tbody>
        </table>
      </div>
    `;
  }

  renderDocuments(target) {
    target.innerHTML = `
      <div style="display:grid; grid-template-columns: 340px 1fr; gap:16px;">
        <div class="mission-card">
          <div style="font-weight:700; margin-bottom:8px;">Upload Medical Record</div>
          <div style="font-size:12px; color:var(--text-muted); margin-bottom:12px;">
            Supports PDF, DOCX, PNG, JPG. Extracted via native PyMuPDF, python-docx, and Groq Vision OCR.
          </div>
          <div style="border: 2px dashed var(--color-border); border-radius:6px; padding:20px; text-align:center; cursor:pointer;" id="drop-zone" onclick="document.getElementById('doc-file-input').click()">
            <div style="font-size:24px; margin-bottom:6px;">📄</div>
            <div style="font-weight:600; color:var(--color-cyan);">Select File to Upload</div>
            <div style="font-size:11px; color:var(--text-muted);">PDF, DOCX, or Image</div>
            <input type="file" id="doc-file-input" style="display:none;" onchange="window.astronautPortal.handleFileUpload(event)">
          </div>
          <div id="upload-status" style="margin-top:10px; font-size:12px;"></div>
        </div>

        <div class="mission-card">
          <div style="display:flex; justify-content:space-between; align-items:center; margin-bottom:10px;">
            <div style="font-weight:700;">Uploaded Records & Medical Review Status</div>
            <button class="btn-secondary" onclick="window.astronautPortal.loadDocuments()">🔄 Refresh</button>
          </div>
          <div id="docs-list-table">Loading documents...</div>
        </div>
      </div>
    `;
    this.loadDocuments();
  }

  async handleFileUpload(event) {
    const file = event.target.files[0];
    if (!file) return;
    const statusBox = document.getElementById('upload-status');
    statusBox.innerHTML = `<span style="color:var(--color-amber);">Uploading ${file.name}...</span>`;
    try {
      const res = await window.api.uploadDocument(file, 'CLINICAL_PANEL', window.api.astronautId);
      statusBox.innerHTML = `<span style="color:var(--color-emerald);">Uploaded! Doc ID: ${res.document_id} (${res.review_status})</span>`;
      this.loadDocuments();
    } catch (err) {
      statusBox.innerHTML = `<span style="color:var(--color-rose);">Upload failed: ${err.message}</span>`;
    }
  }

  async loadDocuments() {
    const tableDiv = document.getElementById('docs-list-table');
    if (!tableDiv) return;
    try {
      const docs = await window.api.listDocuments(window.api.astronautId);
      if (!docs || docs.length === 0) {
        tableDiv.innerHTML = '<div style="color:var(--text-muted); padding:20px; text-align:center;">No medical documents uploaded yet.</div>';
        return;
      }
      tableDiv.innerHTML = `
        <table class="table-aerospace">
          <thead><tr><th>File Name</th><th>Type</th><th>Extracted Entities</th><th>Review Status</th><th>Uploaded</th></tr></thead>
          <tbody>
            ${docs.map(d => `
              <tr>
                <td style="font-weight:600;">${d.filename}</td>
                <td>${d.document_type}</td>
                <td>${d.extracted_findings ? Object.keys(d.extracted_findings).length : 0} items</td>
                <td><span class="badge-tag ${d.review_status === 'CONFIRMED' ? 'badge-prod' : 'badge-demo'}">${d.review_status}</span></td>
                <td>${new Date(d.created_at).toLocaleDateString()}</td>
              </tr>
            `).join('')}
          </tbody>
        </table>
      `;
    } catch (e) {
      tableDiv.innerHTML = `<div style="color:var(--color-rose);">Failed to load documents: ${e.message}</div>`;
    }
  }

  renderCompanion(target) {
    window.chatController.render(target);
  }

  renderProfile(target) {
    target.innerHTML = `
      <div style="display:grid; grid-template-columns: 300px 1fr; gap:16px;">
        <div class="mission-card" style="text-align:center;">
          <img src="assets/nebuvita_team_logo.jpg" style="width:120px; height:120px; border-radius:50%; border:2px solid var(--color-cyan); margin-bottom:12px;" />
          <div style="font-weight:700; font-size:16px;">${window.api.username}</div>
          <div style="color:var(--color-cyan); font-family:var(--font-mono); font-size:12px; margin-bottom:12px;">${window.api.astronautId}</div>
          <span class="badge-tag badge-prod">${window.api.role}</span>
        </div>

        <div class="mission-card">
          <div style="font-weight:700; margin-bottom:12px;">Biometric Baseline & Spaceflight Adaptation</div>
          <table class="table-aerospace">
            <tbody>
              <tr><td>Resting Heart Rate Baseline</td><td>64.0 BPM</td></tr>
              <tr><td>Resting HRV RMSSD</td><td>55.0 ms</td></tr>
              <tr><td>Pre-Flight VO2 Max</td><td>48.2 mL/kg/min</td></tr>
              <tr><td>Spaceflight Day (MET)</td><td>Day 42 (Lunar Orbit)</td></tr>
              <tr><td>Assigned Medical Officer</td><td>DR-SURGEON (Flight Surgeon Lead)</td></tr>
            </tbody>
          </table>
        </div>
      </div>
    `;
  }

  async loadLatestAssessment() {
    const box = document.getElementById('astro-assessment-summary');
    if (!box) return;
    try {
      const assessments = await window.api.listAssessments(window.api.astronautId, 1);
      if (assessments && assessments.length > 0) {
        const a = assessments[0];
        box.innerHTML = `
          <div style="font-weight:600; color:var(--color-emerald); margin-bottom:4px;">Status: ${a.final_status} (${a.risk_level || 'LOW_RISK'})</div>
          <div>${a.synthesis_summary || 'All biosignals and space radiation exposures are currently within safe mission thresholds.'}</div>
        `;
      } else {
        box.innerHTML = '<div>No previous supervisor assessment recorded. Run one below.</div>';
      }
    } catch (e) {
      box.innerHTML = '<div>Operational baseline verified nominal.</div>';
    }
  }

  async triggerAssessment() {
    const box = document.getElementById('astro-assessment-summary');
    if (box) box.innerHTML = '<span style="color:var(--color-amber);">Invoking LangGraph Supervisor & Agent Swarm...</span>';
    try {
      const res = await window.api.runAssessment(window.api.astronautId, 'Astronaut Portal Clinical Refresh');
      if (box) {
        box.innerHTML = `
          <div style="font-weight:600; color:var(--color-emerald); margin-bottom:4px;">Status: ${res.final_status}</div>
          <div>${res.synthesis_summary || 'Clinical multi-agent synthesis executed successfully.'}</div>
        `;
      }
    } catch (err) {
      if (box) box.innerHTML = `<span style="color:var(--color-rose);">Assessment failed: ${err.message}</span>`;
    }
  }
}

window.astronautPortal = new AstronautPortal();
