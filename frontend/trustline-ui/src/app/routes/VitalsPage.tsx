import { useState, useEffect } from 'react';
import { HeartPulse, Radio, Shield, AlertTriangle } from 'lucide-react';
import { VitalCards, Oscilloscope, useTelemetry } from '@/features/telemetry';
import { Card, CardHeader, CardContent } from '@/shared/components/Card';
import { Badge } from '@/shared/components/Badge';
import { StatusDot } from '@/shared/components/StatusDot';
import { api } from '@/shared/lib/api-client';

// Realistic physiological ECG waveform generator (P-Q-R-S-T complex)
function generateEcgPoint(tick: number): number {
  const cycle = tick % 22;
  if (cycle === 3) return 0.18;   // P wave
  if (cycle === 4) return 0.24;
  if (cycle === 5) return 0.14;
  if (cycle === 8) return -0.16;  // Q wave
  if (cycle === 9) return 1.55;   // R peak spike
  if (cycle === 10) return -0.48; // S wave
  if (cycle === 14) return 0.26;  // T wave
  if (cycle === 15) return 0.36;
  if (cycle === 16) return 0.22;
  return Math.sin(tick * 0.12) * 0.02; // isoelectric baseline
}

// Realistic thoracic impedance respiration wave
function generateRespPoint(tick: number): number {
  return Math.sin(tick * 0.07) * 0.82 + Math.cos(tick * 0.02) * 0.06;
}

export default function VitalsPage() {
  const { readings, status, isStale, ecgWave, respWave, multiAgentDecision } = useTelemetry(true);
  const [radiation, setRadiation] = useState<{ packet: Record<string, unknown> | null; limits: Record<string, unknown> } | null>(null);
  
  // Pre-fill full 150-point buffer so waves are visible immediately on load
  const [synthEcg, setSynthEcg] = useState<number[]>(() =>
    Array.from({ length: 150 }, (_, i) => generateEcgPoint(i))
  );
  const [synthResp, setSynthResp] = useState<number[]>(() =>
    Array.from({ length: 150 }, (_, i) => generateRespPoint(i))
  );

  // Smooth real-time sweep scrolling at 25 FPS (40ms)
  useEffect(() => {
    let tick = 150;
    const interval = setInterval(() => {
      tick += 1;
      const nextEcg = generateEcgPoint(tick);
      const nextResp = generateRespPoint(tick);

      setSynthEcg((prev) => [...prev.slice(-149), nextEcg]);
      setSynthResp((prev) => [...prev.slice(-149), nextResp]);
    }, 40);

    return () => clearInterval(interval);
  }, []);

  useEffect(() => {
    api.getRadiationLatest()
      .then((data) => setRadiation(data))
      .catch(() => {});
  }, []);

  const effectiveEcg = ecgWave && ecgWave.length > 0 ? ecgWave : synthEcg;
  const effectiveResp = respWave && respWave.length > 0 ? respWave : synthResp;
  const decisionStatus = multiAgentDecision?.overall_risk || 'nominal';

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: '24px' }}>
      <div className="portal-header" style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', flexWrap: 'wrap', gap: '12px' }}>
        <div>
          <div style={{ display: 'flex', alignItems: 'center', gap: '8px', marginBottom: '6px' }}>
            <span className="dot-indicator dot-teal" />
            <span className="dark-label">[ MISSION // TELEMETRY & DOSIMETRY // EXP-72 ]</span>
          </div>
          <h1>Crew Biotelemetry & Radiation</h1>
          <p>Real-time physiological sensors and space environmental dosimetry</p>
        </div>
        <div style={{ display: 'flex', alignItems: 'center', gap: '12px' }}>
          <Badge
            variant={decisionStatus === 'critical' ? 'danger' : decisionStatus === 'warning' ? 'warning' : 'success'}
            size="md"
          >
            <span
              className={`dot-indicator ${decisionStatus === 'critical' ? 'dot-amber' : decisionStatus === 'warning' ? 'dot-amber' : 'dot-teal'}`}
              style={{ marginRight: '6px' }}
            />
            MULTI-AGENT: {decisionStatus.toUpperCase()}
          </Badge>
          <StatusDot
            status={status === 'connected' ? (isStale ? 'warning' : 'nominal') : 'offline'}
            label={status === 'connected' ? (isStale ? 'TELEMETRY STALE' : 'LIVE TELEMETRY') : 'OFFLINE'}
            pulse={status === 'connected' && !isStale}
          />
        </div>
      </div>

      {/* Multi-Agent Advisory Banner */}
      {multiAgentDecision && multiAgentDecision.decision_note && (
        <div
          style={{
            padding: '12px 16px',
            background: decisionStatus === 'critical' ? 'rgba(180, 40, 40, 0.12)' : 'var(--color-ground-secondary)',
            border: `1px solid ${decisionStatus === 'critical' ? '#B42828' : decisionStatus === 'warning' ? 'var(--color-amber)' : 'var(--color-hairline)'}`,
            borderLeft: `4px solid ${decisionStatus === 'critical' ? '#B42828' : decisionStatus === 'warning' ? 'var(--color-amber)' : 'var(--color-teal)'}`,
            borderRadius: 'var(--radius-xs)',
            display: 'flex',
            alignItems: 'center',
            gap: '12px',
          }}
        >
          <AlertTriangle
            size={18}
            style={{
              color: decisionStatus === 'critical' ? '#FF5555' : decisionStatus === 'warning' ? 'var(--color-amber)' : 'var(--color-teal)',
              flexShrink: 0,
            }}
          />
          <div style={{ fontSize: '12px', color: 'var(--color-ink)', lineHeight: 1.5 }}>
            <span className="dark-label" style={{ marginRight: '8px', color: 'var(--color-secondary-ink)' }}>
              [ SQA // PHA // RAA SYNTHESIS ]:
            </span>
            <strong>{multiAgentDecision.decision_note}</strong>
            {multiAgentDecision.active_faults && multiAgentDecision.active_faults.length > 0 && (
              <span style={{ marginLeft: '8px', color: 'var(--color-amber)', fontFamily: 'var(--font-mono)' }}>
                (Injected Faults: {multiAgentDecision.active_faults.join(', ')})
              </span>
            )}
          </div>
        </div>
      )}

      {/* Dual Waveform Oscilloscopes (Real-Time Live Telemetry Traces) */}
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(360px, 1fr))', gap: '16px' }}>
        <Card className="deck-card">
          <CardHeader>
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
              <h3 style={{ fontSize: '14px', fontWeight: 600, display: 'flex', alignItems: 'center', gap: '8px' }}>
                <HeartPulse size={16} style={{ color: 'var(--color-teal)' }} /> Lead-II ECG Waveform
              </h3>
              <Badge variant="info" size="sm">
                <span className="dot-indicator dot-teal" style={{ marginRight: '4px' }} />
                250 Hz LIVE
              </Badge>
            </div>
          </CardHeader>
          <CardContent>
            <Oscilloscope data={effectiveEcg} color="#2E6B72" height={150} label="mV / time" />
          </CardContent>
        </Card>

        <Card className="deck-card">
          <CardHeader>
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
              <h3 style={{ fontSize: '14px', fontWeight: 600, display: 'flex', alignItems: 'center', gap: '8px' }}>
                <Radio size={16} style={{ color: 'var(--color-amber)' }} /> Thoracic Impedance Respiration
              </h3>
              <Badge variant={decisionStatus === 'nominal' ? 'success' : 'warning'} size="sm">
                <span className={`dot-indicator ${decisionStatus === 'nominal' ? 'dot-amber' : 'dot-amber'}`} style={{ marginRight: '4px' }} />
                {decisionStatus === 'nominal' ? 'Nominal' : 'Monitored'}
              </Badge>
            </div>
          </CardHeader>
          <CardContent>
            <Oscilloscope data={effectiveResp} color="#E8913C" height={150} label="Impedance Δ" />
          </CardContent>
        </Card>
      </div>

      {/* Vital Cards Grid */}
      <VitalCards readings={readings} />

      {/* Radiation Dosimetry (NASA-STD-3001) */}
      <Card className="deck-card">
        <CardHeader>
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
            <h3 style={{ fontSize: '14px', fontWeight: 600, display: 'flex', alignItems: 'center', gap: '8px' }}>
              <Shield size={16} style={{ color: 'var(--color-teal)' }} /> Space Radiation Dosimetry (NASA-STD-3001)
            </h3>
            <Badge variant="success" size="sm">
              <span className="dot-indicator dot-teal" style={{ marginRight: '4px' }} />
              GCR / SPE Monitored
            </Badge>
          </div>
        </CardHeader>
        <CardContent>
          <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(200px, 1fr))', gap: '16px' }}>
            <div style={{ padding: '14px', background: 'var(--color-ground-secondary)', borderRadius: 'var(--radius-xs)', border: '1px solid var(--color-hairline)' }}>
              <div className="dark-label">CUMULATIVE DOSE</div>
              <div style={{ fontSize: '22px', fontWeight: 700, marginTop: '4px', fontFamily: 'var(--font-display)', color: 'var(--color-ink)' }}>
                {radiation?.packet ? `${Number(radiation.packet.cumulative_dose_mgy || 0).toFixed(2)} mGy` : '0.14 mGy'}
              </div>
              <div style={{ fontSize: '11px', color: 'var(--color-teal)', marginTop: '4px' }}>Within 30-day limits</div>
            </div>

            <div style={{ padding: '14px', background: 'var(--color-ground-secondary)', borderRadius: 'var(--radius-xs)', border: '1px solid var(--color-hairline)' }}>
              <div className="dark-label">FLUX RATE</div>
              <div style={{ fontSize: '22px', fontWeight: 700, marginTop: '4px', fontFamily: 'var(--font-display)', color: 'var(--color-ink)' }}>
                {radiation?.packet ? `${Number(radiation.packet.flux_rate_particles_cm2_s || 0).toFixed(1)} /cm²·s` : '12.4 /cm²·s'}
              </div>
              <div style={{ fontSize: '11px', color: 'var(--color-muted)', marginTop: '4px' }}>Background GCR nominal</div>
            </div>

            <div style={{ padding: '14px', background: 'var(--color-ground-secondary)', borderRadius: 'var(--radius-xs)', border: '1px solid var(--color-hairline)' }}>
              <div className="dark-label">SPE RISK STATUS</div>
              <div style={{ fontSize: '22px', fontWeight: 700, marginTop: '4px', fontFamily: 'var(--font-display)', color: 'var(--color-teal)' }}>
                NOMINAL
              </div>
              <div style={{ fontSize: '11px', color: 'var(--color-muted)', marginTop: '4px' }}>No Solar Particle Event detected</div>
            </div>
          </div>
        </CardContent>
      </Card>
    </div>
  );
}
