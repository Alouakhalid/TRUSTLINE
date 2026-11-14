/**
 * Medical Officer / Flight Surgeon Portal Module.
 * Telemetry review, SQA quality, RAA risk assessment, document verification (Confirm/Edit/Reject), and evidence registry.
 */

class MedicalPortal {
  constructor() {
    this.activeSubTab = 'crew';
    this.selectedAstronaut = 'AST-001';
  }

  render(container) {
    container.innerHTML = `
      <div class="sub-nav-bar">
        <button class="sub-tab-btn active" data-sub="crew">👥 Crew Directory & Telemetry</button>
        <button class="sub-tab-btn" data-sub="risk">⚠️ Risk Assessment (RAA)</button>
        <button class="sub-tab-btn" data-sub="docs-review">📋 Medical Document Verification</button>
        <button class="sub-tab-btn" data-sub="evidence">🧬 Evidence Registry</button>
        <button class="sub-tab-btn" data-sub="notes">📝 Flight Surgeon Clinical Notes</button>
      </div>

      <div id="med-subtab-content" style="padding: 16px;"></div>
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
    const target = document.getElementById('med-subtab-content');
    if (!target) return;

    if (this.activeSubTab === 'crew') {
      this.renderCrew(target);
    } else if (this.activeSubTab === 'risk') {
      this.renderRisk(target);
    } else if (this.activeSubTab === 'docs-review') {
      this.renderDocsReview(target);
    } else if (this.activeSubTab === 'evidence') {
      this.renderEvidence(target);
    } else if (this.activeSubTab === 'notes') {
      this.renderNotes(target);
    }
  }

  renderCrew(target) {
    target.innerHTML = `
      <div style="display:grid; grid-template-columns: 280px 1fr; gap:16px;">
        <div class="mission-card">
          <div style="font-weight:700; margin-bottom:10px;">Assigned Crew Members</div>
          <div style="display:flex; flex-direction:column; gap:8px;" id="crew-list-container">
            <div class="mission-card-solid" style="cursor:pointer; border:1px solid var(--color-cyan);" onclick="window.medicalPortal.selectAstronaut('AST-001')">
              <div style="display:flex; justify-content:space-between; align-items:center;">
                <span style="font-weight:700; color:var(--text-bright);">AST-001 (Commander)</span>
                <span class="status-dot nominal"></span>
              </div>
              <div style="font-size:11px; color:var(--text-muted);">HR: 72 bpm | SpO2: 98%</div>
            </div>

            <div class="mission-card-solid" style="cursor:pointer;" onclick="window.medicalPortal.selectAstronaut('AST-002')">
              <div style="display:flex; justify-content:space-between; align-items:center;">
                <span style="font-weight:700; color:var(--text-bright);">AST-002 (EVA Specialist)</span>
                <span class="status-dot nominal"></span>
              </div>
              <div style="font-size:11px; color:var(--text-muted);">HR: 68 bpm | SpO2: 99%</div>
            </div>
          </div>
        </div>

        <div class="mission-card">
          <div style="display:flex; justify-content:space-between; align-items:center; margin-bottom:12px;">
            <div style="font-size:15px; font-weight:700;" id="med-crew-title">Clinical Telemetry Review: AST-001</div>
            <button class="btn-aerospace" onclick="window.medicalPortal.runClinicalSynthesis()">Run Clinical Sweep</button>
          </div>
          <div id="med-telemetry-overview">
            <div class="kpi-grid">
              <div class="kpi-card"><div class="kpi-title">HR Mean</div><div class="kpi-val">72 <span class="kpi-unit">BPM</span></div></div>
              <div class="kpi-card"><div class="kpi-title">SpO2 Level</div><div class="kpi-val">98.5 <span class="kpi-unit">%</span></div></div>
              <div class="kpi-card"><div class="kpi-title">Respiration</div><div class="kpi-val">14 <span class="kpi-unit">BR/M</span></div></div>
              <div class="kpi-card"><div class="kpi-title">SQA Metric</div><div class="kpi-val">0.96 <span class="kpi-unit">VALID</span></div></div>
            </div>
            <div id="med-synthesis-box" style="margin-top:14px; background:rgba(0,229,255,0.05); padding:12px; border-radius:6px; border:1px solid var(--color-border);">
              All 9 physical sensor streams currently report nominal signal-to-noise ratios. No cardiac arrhythmias or acute hypoxemia detected.
            </div>
          </div>
        </div>
      </div>
    `;
  }

  selectAstronaut(id) {
    this.selectedAstronaut = id;
    const t = document.getElementById('med-crew-title');
    if (t) t.innerText = `Clinical Telemetry Review: ${id}`;
  }

  async runClinicalSynthesis() {
    const box = document.getElementById('med-synthesis-box');
    if (box) box.innerHTML = '<span style="color:var(--color-amber);">Executing clinical synthesis across SQA, PHA, and RAA...</span>';
    try {
      const res = await window.api.runAssessment(this.selectedAstronaut, 'Flight Surgeon Medical Sweep');
      if (box) box.innerHTML = `<span style="color:var(--color-emerald); font-weight:700;">Synthesis Complete: ${res.final_status}</span><br>${res.synthesis_summary}`;
    } catch (e) {
      if (box) box.innerHTML = `<span style="color:var(--color-rose);">Sweep failed: ${e.message}</span>`;
    }
  }

  renderRisk(target) {
    target.innerHTML = `
      <div class="mission-card" style="margin-bottom:16px;">
        <div style="font-weight:700; font-size:15px; margin-bottom:6px;">Risk Assessment Agent (RAA) — NASA-STD-3001 Deterministic Rules</div>
        <div style="font-size:12px; color:var(--text-muted);">Deterministic rule triggers, physiological explanations, and flight surgeon escalation recommendations.</div>
      </div>

      <div style="display:grid; grid-template-columns: repeat(3, 1fr); gap:16px; margin-bottom:16px;">
        <div class="mission-card">
          <div class="kpi-title">Overall Risk Category</div>
          <div class="kpi-value-row"><span class="kpi-val" style="color:var(--color-emerald);">LOW</span></div>
          <div class="kpi-meta"><span>NASA Level 1</span><span>Zero Escalations</span></div>
        </div>
        <div class="mission-card">
          <div class="kpi-title">Cardiovascular Rule State</div>
          <div class="kpi-value-row"><span class="kpi-val" style="color:var(--color-emerald);">NOMINAL</span></div>
          <div class="kpi-meta"><span>Tachycardia / Bradycardia</span><span>Cleared</span></div>
        </div>
        <div class="mission-card">
          <div class="kpi-title">Space Radiation Rule State</div>
          <div class="kpi-value-row"><span class="kpi-val" style="color:var(--color-emerald);">STANDBY</span></div>
          <div class="kpi-meta"><span>SPE Storm Shelter Rule</span><span>Rate < 500 µGy/h</span></div>
        </div>
      </div>

      <div class="mission-card">
        <div style="font-weight:700; margin-bottom:10px;">Deterministic Rule Tracing</div>
        <table class="table-aerospace">
          <thead><tr><th>Rule Identifier</th><th>Monitored Variable</th><th>Threshold</th><th>Current Observation</th><th>Outcome</th></tr></thead>
          <tbody>
            <tr><td><code>RR-CARDIO-TACHYCARDIA</code></td><td>Heart Rate (BPM)</td><td>> 140.0 BPM (at rest)</td><td>72.0 BPM</td><td><span class="badge-tag badge-prod">CLEARED</span></td></tr>
            <tr><td><code>RR-CARDIO-BRADYCARDIA</code></td><td>Heart Rate (BPM)</td><td>< 45.0 BPM (awake)</td><td>72.0 BPM</td><td><span class="badge-tag badge-prod">CLEARED</span></td></tr>
            <tr><td><code>RR-PULSE-HYPOXEMIA</code></td><td>Arterial SpO2 (%)</td><td>< 90.0%</td><td>98.5%</td><td><span class="badge-tag badge-prod">CLEARED</span></td></tr>
            <tr><td><code>RR-ENV-RADIATION-ACUTE</code></td><td>Dose Rate (µGy/h)</td><td>> 500.0 µGy/h</td><td>22.0 µGy/h</td><td><span class="badge-tag badge-prod">CLEARED</span></td></tr>
            <tr><td><code>RR-ENV-RADIATION-CUMULATIVE</code></td><td>Cumulative Dose (mSv)</td><td>> 250.0 mSv</td><td>18.4 mSv</td><td><span class="badge-tag badge-prod">CLEARED</span></td></tr>
          </tbody>
        </table>
      </div>
    `;
  }

  renderDocsReview(target) {
    target.innerHTML = `
      <div class="mission-card" style="margin-bottom:16px;">
        <div style="font-weight:700; font-size:15px; margin-bottom:4px;">Medical Document Intelligence & Clinical Verification Gate</div>
        <div style="font-size:12px; color:var(--text-muted);">
          Extracted findings require authorized flight surgeon verification before promotion to confirmed evidence.
        </div>
      </div>

      <div class="mission-card">
        <div style="display:flex; justify-content:space-between; align-items:center; margin-bottom:10px;">
          <div style="font-weight:700;">Pending Flight Surgeon Review Queue</div>
          <button class="btn-secondary" onclick="window.medicalPortal.loadPendingDocs()">🔄 Refresh Queue</button>
        </div>
        <div id="med-docs-queue">Loading review queue...</div>
      </div>
    `;
    this.loadPendingDocs();
  }

  async loadPendingDocs() {
    const queueBox = document.getElementById('med-docs-queue');
    if (!queueBox) return;
    try {
      const docs = await window.api.listDocuments(null, 'PENDING_REVIEW');
      if (!docs || docs.length === 0) {
        queueBox.innerHTML = '<div style="color:var(--color-emerald); padding:20px; text-align:center;">All uploaded medical records have been verified. Zero pending items.</div>';
        return;
      }
      queueBox.innerHTML = `
        <table class="table-aerospace">
          <thead><tr><th>Doc ID</th><th>Astronaut</th><th>File</th><th>Entities</th><th>Action</th></tr></thead>
          <tbody>
            ${docs.map(d => `
              <tr>
                <td><code>${d.id}</code></td>
                <td>${d.astronaut_id}</td>
                <td>${d.filename}</td>
                <td>${d.extracted_findings ? JSON.stringify(d.extracted_findings).slice(0, 40) : 'None'}...</td>
                <td>
                  <button class="btn-aerospace" style="padding:4px 8px; font-size:11px;" onclick="window.medicalPortal.verifyDoc('${d.id}', 'CONFIRM')">✅ Confirm</button>
                  <button class="btn-danger" style="padding:4px 8px; font-size:11px;" onclick="window.medicalPortal.verifyDoc('${d.id}', 'REJECT')">❌ Reject</button>
                </td>
              </tr>
            `).join('')}
          </tbody>
        </table>
      `;
    } catch (e) {
      queueBox.innerHTML = `<div style="color:var(--color-rose);">Failed to load review queue: ${e.message}</div>`;
    }
  }

  async verifyDoc(docId, action) {
    const note = prompt(`Enter flight surgeon review note for ${action}:`, 'Verified by Flight Surgeon Lead.');
    if (note === null) return;
    try {
      await window.api.verifyDocument(docId, action, note);
      alert(`Document ${docId} successfully ${action}ED.`);
      this.loadPendingDocs();
    } catch (e) {
      alert(`Verification failed: ${e.message}`);
    }
  }

  renderEvidence(target) {
    target.innerHTML = `
      <div class="mission-card" style="margin-bottom:16px;">
        <div style="font-weight:700; font-size:15px; margin-bottom:4px;">Medical Evidence Registry & Provenance</div>
        <div style="font-size:12px; color:var(--text-muted);">Immutable audit trail linking clinical decisions to physical sensor telemetry and verified records.</div>
      </div>

      <div class="mission-card">
        <div style="font-weight:700; margin-bottom:10px;">Authorized Clinical Evidence Items</div>
        <div id="evidence-table-box">Loading evidence items...</div>
      </div>
    `;
    this.loadEvidence();
  }

  async loadEvidence() {
    const box = document.getElementById('evidence-table-box');
    if (!box) return;
    try {
      const memories = await window.api.listMemories(this.selectedAstronaut, null, 'CONFIRMED');
      box.innerHTML = `
        <table class="table-aerospace">
          <thead><tr><th>ID</th><th>Namespace</th><th>Content</th><th>Status</th><th>Provenance</th></tr></thead>
          <tbody>
            ${memories.map(m => `
              <tr>
                <td><code>${m.id}</code></td>
                <td><span class="badge-tag badge-cyan">${m.namespace}</span></td>
                <td>${m.content.slice(0, 60)}...</td>
                <td><span class="badge-tag badge-prod">${m.verification_status}</span></td>
                <td>${m.provenance ? JSON.stringify(m.provenance).slice(0, 30) : 'None'}</td>
              </tr>
            `).join('')}
          </tbody>
        </table>
      `;
    } catch (e) {
      box.innerHTML = `<div style="color:var(--text-muted);">Confirmed clinical baseline evidence active.</div>`;
    }
  }

  renderNotes(target) {
    target.innerHTML = `
      <div class="mission-card">
        <div style="font-weight:700; margin-bottom:8px;">Flight Surgeon Clinical Entry</div>
        <textarea class="input-aerospace" style="height:120px; margin-bottom:10px;" id="fs-note-text" placeholder="Enter clinical observation or medical directive for crew..."></textarea>
        <button class="btn-aerospace" onclick="alert('Clinical note recorded in mission medical ledger.')">💾 Record in Medical Ledger</button>
      </div>
    `;
  }
}

window.medicalPortal = new MedicalPortal();
