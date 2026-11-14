import { SimulatorPanel } from '@/features/simulator';
import { Card, CardHeader, CardContent } from '@/shared/components/Card';
import { Activity, Cpu, Sliders, Zap } from 'lucide-react';

export default function SimulatorPage() {
  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: '24px' }}>
      <div className="portal-header">
        <div style={{ display: 'flex', alignItems: 'center', gap: '8px', marginBottom: '6px' }}>
          <span className="dot-indicator dot-teal" />
          <span className="dark-label">[ HARDWARE SIMULATION // 10-SENSOR ODE ENGINE // EXP-72 ]</span>
        </div>
        <h1>Biomedical Sensor Simulator & Stress Engine</h1>
        <p>10-sensor physiological generator with fault injection and flight scenario emulation</p>
      </div>

      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(320px, 1fr))', gap: '20px' }}>
        <SimulatorPanel />

        <div style={{ display: 'flex', flexDirection: 'column', gap: '16px' }}>
          <Card className="deck-card">
            <CardHeader>
              <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
                <span className="dot-indicator dot-bone" />
                <h3 style={{ fontSize: '14px', fontWeight: 600, display: 'flex', alignItems: 'center', gap: '8px' }}>
                  <Cpu size={16} style={{ color: 'var(--color-teal)' }} /> Signal Models Architecture
                </h3>
              </div>
            </CardHeader>
            <CardContent>
              <div style={{ display: 'flex', flexDirection: 'column', gap: '14px', fontSize: '13px', color: 'var(--color-ink-secondary)' }}>
                <div style={{ display: 'flex', alignItems: 'flex-start', gap: '10px' }}>
                  <Activity size={16} style={{ color: 'var(--color-teal)', flexShrink: 0, marginTop: '2px' }} />
                  <div>
                    <strong style={{ color: 'var(--color-ink)' }}>Cardiac & Hemodynamic:</strong> Synthetic Lead-II ECG generator with autonomous HRV modulation and blood pressure waveform coupling.
                  </div>
                </div>

                <div className="rule-teal" style={{ height: '1px', width: '100%' }} />

                <div style={{ display: 'flex', alignItems: 'flex-start', gap: '10px' }}>
                  <Zap size={16} style={{ color: 'var(--color-amber)', flexShrink: 0, marginTop: '2px' }} />
                  <div>
                    <strong style={{ color: 'var(--color-ink)' }}>Autonomic & Thermal:</strong> Electrodermal activity (tonic + phasic skin conductance) with deep-space cabin thermoregulation.
                  </div>
                </div>

                <div className="rule-amber" style={{ height: '1px', width: '100%' }} />

                <div style={{ display: 'flex', alignItems: 'flex-start', gap: '10px' }}>
                  <Sliders size={16} style={{ color: 'var(--color-teal)', flexShrink: 0, marginTop: '2px' }} />
                  <div>
                    <strong style={{ color: 'var(--color-ink)' }}>Fault Injection:</strong> Non-destructive synthetic faults (flatline, drift, clipping, Gaussian noise) for validating agent detection pipelines.
                  </div>
                </div>
              </div>
            </CardContent>
          </Card>
        </div>
      </div>
    </div>
  );
}
