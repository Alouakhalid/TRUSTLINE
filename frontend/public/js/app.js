/**
 * Main TRUSTLINE Application Orchestrator.
 * Coordinates role switching, navigation, live telemetry binding, and UTC mission clock.
 */

class TrustlineApp {
  constructor() {
    this.currentPortal = 'astronaut';
    this.init();
  }

  init() {
    console.log('[TRUSTLINE] Booting Aerospace Portal System...');
    this.setupNavigation();
    this.setupClock();
    this.setupDemoMode();
    this.setupRoleSwitcher();
    this.setupTelemetryBinding();

    // Default portal
    this.switchPortal('astronaut');

    // Connect real-time telemetry stream
    window.telemetryStream.connect();
  }

  setupNavigation() {
    document.querySelectorAll('.nav-tab-btn').forEach(btn => {
      btn.addEventListener('click', () => {
        document.querySelectorAll('.nav-tab-btn').forEach(b => b.classList.remove('active'));
        btn.classList.add('active');
        const portal = btn.getAttribute('data-portal');
        this.switchPortal(portal);
      });
    });
  }

  switchPortal(portal) {
    this.currentPortal = portal;
    const container = document.getElementById('portal-view-container');
    if (!container) return;

    if (portal === 'astronaut') {
      window.astronautPortal.render(container);
    } else if (portal === 'medical') {
      window.medicalPortal.render(container);
    } else if (portal === 'admin') {
      window.adminPortal.render(container);
    }
  }

  setupClock() {
    const clockEl = document.getElementById('mission-clock');
    if (!clockEl) return;
    const update = () => {
      const now = new Date();
      clockEl.innerText = `${now.toISOString().slice(11, 19)} UTC`;
    };
    update();
    setInterval(update, 1000);
  }

  setupDemoMode() {
    const demoBtn = document.getElementById('demo-toggle-btn');
    if (!demoBtn) return;
    const updateUi = () => {
      if (window.api.isDemo) {
        demoBtn.className = 'badge-tag badge-demo';
        demoBtn.innerText = 'MODE: DEMO (ISOLATED)';
      } else {
        demoBtn.className = 'badge-tag badge-prod';
        demoBtn.innerText = 'MODE: OPERATIONAL';
      }
    };
    updateUi();
    demoBtn.addEventListener('click', () => {
      window.api.setDemoMode(!window.api.isDemo);
      updateUi();
      alert(`Switched to ${window.api.isDemo ? 'DEMO MODE (Isolated partition)' : 'OPERATIONAL MODE'}. Refreshing view...`);
      window.location.reload();
    });
  }

  setupRoleSwitcher() {
    const sel = document.getElementById('role-select');
    if (!sel) return;
    sel.value = window.api.role || 'ASTRONAUT';
    sel.addEventListener('change', async (e) => {
      const newRole = e.target.value;
      const username = newRole === 'ADMINISTRATOR' ? 'chief_admin' : (newRole === 'MEDICAL_OFFICER' ? 'flight_surgeon_1' : 'astronaut_1');
      try {
        await window.api.register(username, 'a-very-strong-space-password', newRole, 'AST-001').catch(() => {});
        await window.api.login(username, 'a-very-strong-space-password');
        alert(`Logged in as ${newRole} (${username}).`);
        window.location.reload();
      } catch (err) {
        alert(`Login failed: ${err.message}`);
      }
    });
  }

  setupTelemetryBinding() {
    window.telemetryStream.subscribe((pkt) => {
      // 1. Update KPI numbers if on overview
      if (pkt.sensor_type === 'HR' && pkt.channels_data && pkt.channels_data[0]) {
        const val = pkt.channels_data[0][0];
        const el = document.getElementById('val-hr');
        if (el) el.innerText = Math.round(val);
      }
      if (pkt.sensor_type === 'SPO2' && pkt.channels_data && pkt.channels_data[0]) {
        const val = pkt.channels_data[0][0];
        const el = document.getElementById('val-spo2');
        if (el) el.innerText = Number(val).toFixed(1);
      }
      if (pkt.sensor_type === 'CORE_TEMP' && pkt.channels_data && pkt.channels_data[0]) {
        const val = pkt.channels_data[0][0];
        const el = document.getElementById('val-core');
        if (el) el.innerText = Number(val).toFixed(1);
      }
      if (pkt.sensor_type === 'SKIN_TEMP' && pkt.channels_data && pkt.channels_data[0]) {
        const val = pkt.channels_data[0][0];
        const el = document.getElementById('val-skin');
        if (el) el.innerText = Number(val).toFixed(1);
      }
      if (pkt.sensor_type === 'EDA' && pkt.channels_data && pkt.channels_data[0]) {
        const val = pkt.channels_data[0][0];
        const el = document.getElementById('val-eda');
        if (el) el.innerText = Number(val).toFixed(2);
      }

      // 2. Feed oscilloscopes
      if (window.astronautPortal && window.astronautPortal.oscilloscopes) {
        const scopes = window.astronautPortal.oscilloscopes;
        if (pkt.sensor_type === 'ECG' && scopes.ecg && pkt.channels_data && pkt.channels_data[1]) {
          scopes.ecg.pushData(pkt.channels_data[1]); // Lead II
        }
        if (pkt.sensor_type === 'PPG' && scopes.ppg && pkt.channels_data && pkt.channels_data[0]) {
          scopes.ppg.pushData(pkt.channels_data[0]);
        }
        if (pkt.sensor_type === 'RESPIRATION' && scopes.resp && pkt.channels_data && pkt.channels_data[0]) {
          scopes.resp.pushData(pkt.channels_data[0]);
        }
        if (pkt.sensor_type === 'EDA' && scopes.eda && pkt.channels_data && pkt.channels_data[0]) {
          scopes.eda.pushData(pkt.channels_data[0]);
        }
      }

      // 3. Update 3D Hotspot beacon quality
      if (window.twin) {
        window.twin.updateHotspotQuality(pkt.sensor_type, 'NOMINAL');
      }
    });

    window.addEventListener('telemetry-status', (e) => {
      const connDot = document.getElementById('conn-status-dot');
      const connText = document.getElementById('conn-status-text');
      if (connDot && connText) {
        if (e.detail.connected) {
          connDot.className = 'status-dot nominal';
          connText.innerText = e.detail.protocol;
        } else {
          connDot.className = 'status-dot critical';
          connText.innerText = 'OFFLINE';
        }
      }
    });
  }
}

window.addEventListener('DOMContentLoaded', () => {
  window.app = new TrustlineApp();
});
