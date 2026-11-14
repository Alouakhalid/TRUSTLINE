import { useRef } from 'react';
import { useNavigate } from 'react-router-dom';
import { HeartPulse, Droplets, Thermometer, Activity, Wind, Zap, MessageSquare, User, Shield, AlertTriangle } from 'lucide-react';
import { Card, CardContent } from '@/shared/components/Card';
import { Badge } from '@/shared/components/Badge';
import { Button } from '@/shared/components/Button';
import { StatusDot } from '@/shared/components/StatusDot';
import { useAuth } from '@/features/auth';
import { AssessmentCard } from '@/features/assessments';
import { useTelemetry } from '@/features/telemetry';
import gsap from 'gsap';
import { useGSAP } from '@gsap/react';

gsap.registerPlugin(useGSAP);

export default function AstronautPortal() {
  const { astronautId } = useAuth();
  const navigate = useNavigate();
  const containerRef = useRef<HTMLDivElement>(null);
  const { readings, status, isStale, multiAgentDecision } = useTelemetry(true);

  const hrVal = readings?.get('heart_rate')?.value ?? readings?.get('hr')?.value ?? readings?.get('HR')?.value ?? 72;
  const hrStatus = readings?.get('heart_rate')?.status ?? 'nominal';

  const spo2Val = readings?.get('spo2')?.value ?? readings?.get('SPO2')?.value ?? 98.4;
  const spo2Status = readings?.get('spo2')?.status ?? 'nominal';

  const tempVal = readings?.get('temperature')?.value ?? readings?.get('core_temp')?.value ?? readings?.get('temp')?.value ?? 36.8;
  const tempStatus = readings?.get('temperature')?.status ?? 'nominal';

  const bpVal = readings?.get('blood_pressure')?.value ?? readings?.get('ppg')?.value;
  const bpDisplay = bpVal ? `${Math.round(bpVal)}/80` : '120/80';
  const bpStatus = readings?.get('blood_pressure')?.status ?? 'nominal';

  const respVal = readings?.get('respiration')?.value ?? readings?.get('resp')?.value ?? 16;
  const respStatus = readings?.get('respiration')?.status ?? 'nominal';

  const edaVal = readings?.get('eda')?.value ?? readings?.get('EDA')?.value ?? 4.2;
  const edaStatus = readings?.get('eda')?.status ?? 'nominal';

  const vitalsList = [
    { icon: HeartPulse, label: 'Heart Rate', value: typeof hrVal === 'number' ? hrVal.toFixed(0) : String(hrVal), unit: 'bpm', status: hrStatus },
    { icon: Droplets, label: 'SpO₂', value: typeof spo2Val === 'number' ? spo2Val.toFixed(1) : String(spo2Val), unit: '%', status: spo2Status },
    { icon: Thermometer, label: 'Core Temp', value: typeof tempVal === 'number' ? tempVal.toFixed(1) : String(tempVal), unit: '°C', status: tempStatus },
    { icon: Activity, label: 'Blood Pressure', value: bpDisplay, unit: 'mmHg', status: bpStatus },
    { icon: Wind, label: 'Respiration', value: typeof respVal === 'number' ? respVal.toFixed(0) : String(respVal), unit: 'br/min', status: respStatus },
    { icon: Zap, label: 'EDA', value: typeof edaVal === 'number' ? edaVal.toFixed(1) : String(edaVal), unit: 'μS', status: edaStatus },
  ];

  useGSAP(() => {
    const mm = gsap.matchMedia();
    mm.add('(prefers-reduced-motion: no-preference)', () => {
      gsap.from('.vital-card', { opacity: 0, y: 20, stagger: 0.06, duration: 0.4, ease: 'power2.out' });
    });
  }, { scope: containerRef });

  const getBadgeVariant = (st: string) => {
    if (st === 'critical') return 'danger';
    if (st === 'warning') return 'warning';
    return 'success';
  };

  const getDotClass = (st: string) => {
    if (st === 'critical' || st === 'warning') return 'dot-amber';
    return 'dot-teal';
  };

  const decisionRisk = multiAgentDecision?.overall_risk || 'nominal';

  return (
    <div ref={containerRef}>
      <div className="portal-header" style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', flexWrap: 'wrap', gap: '12px' }}>
        <div>
          <div style={{ display: 'flex', alignItems: 'center', gap: '8px', marginBottom: '6px' }}>
            <span className="dot-indicator dot-teal" />
            <span className="dark-label">[ CREW BIOMEDICAL MANIFEST // EXP-72 ]</span>
          </div>
          <h1>Astronaut Dashboard</h1>
          <p>Crew Member {astronautId} · {new Date().toLocaleDateString('en-US', { weekday: 'long', year: 'numeric', month: 'long', day: 'numeric' })}</p>
        </div>
        <div style={{ display: 'flex', alignItems: 'center', gap: '12px' }}>
          <Badge
            variant={decisionRisk === 'critical' ? 'danger' : decisionRisk === 'warning' ? 'warning' : 'success'}
            size="md"
          >
            <span
              className={`dot-indicator ${decisionRisk === 'critical' ? 'dot-amber' : decisionRisk === 'warning' ? 'dot-amber' : 'dot-teal'}`}
              style={{ marginRight: '6px' }}
            />
            MULTI-AGENT: {decisionRisk.toUpperCase()}
          </Badge>
          <StatusDot
            status={status === 'connected' ? (isStale ? 'warning' : 'nominal') : 'offline'}
            label={status === 'connected' ? (isStale ? 'TELEMETRY STALE' : 'LIVE TELEMETRY STREAM') : 'OFFLINE'}
            pulse={status === 'connected' && !isStale}
          />
        </div>
      </div>

      {/* Multi-Agent Live Advisory Banner */}
      {multiAgentDecision && multiAgentDecision.decision_note && (
        <div
          style={{
            padding: '12px 16px',
            background: decisionRisk === 'critical' ? 'rgba(180, 40, 40, 0.12)' : 'var(--color-ground-secondary)',
            border: `1px solid ${decisionRisk === 'critical' ? '#B42828' : decisionRisk === 'warning' ? 'var(--color-amber)' : 'var(--color-hairline)'}`,
            borderLeft: `4px solid ${decisionRisk === 'critical' ? '#B42828' : decisionRisk === 'warning' ? 'var(--color-amber)' : 'var(--color-teal)'}`,
            borderRadius: 'var(--radius-xs)',
            display: 'flex',
            alignItems: 'center',
            gap: '12px',
            marginBottom: '20px',
          }}
        >
          <AlertTriangle
            size={18}
            style={{
              color: decisionRisk === 'critical' ? '#FF5555' : decisionRisk === 'warning' ? 'var(--color-amber)' : 'var(--color-teal)',
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
                (Active Faults: {multiAgentDecision.active_faults.join(', ')})
              </span>
            )}
          </div>
        </div>
      )}

      <div className="portal-grid">
        {vitalsList.map((v) => (
          <Card key={v.label} className="vital-card deck-card" variant="default">
            <CardContent>
              <div className="vital-icon">
                <v.icon
                  size={22}
                  style={{
                    color: v.status === 'critical' ? '#FF5555' : v.status === 'warning' ? 'var(--color-amber)' : 'var(--color-teal)',
                    transition: 'color var(--duration-fast)',
                  }}
                />
              </div>
              <div
                className="vital-value"
                style={{
                  color: v.status === 'critical' ? '#FF5555' : v.status === 'warning' ? 'var(--color-amber)' : 'var(--color-ink)',
                  transition: 'color var(--duration-fast)',
                }}
              >
                {v.value}
                <span className="vital-unit">{v.unit}</span>
              </div>
              <div className="vital-label">{v.label}</div>
              <Badge variant={getBadgeVariant(v.status)} size="sm">
                <span className={`dot-indicator ${getDotClass(v.status)}`} style={{ marginRight: '4px' }} />
                {v.status.toUpperCase()}
              </Badge>
            </CardContent>
          </Card>
        ))}
      </div>

      <div className="quick-actions">
        <Button variant="primary" size="md" icon={<MessageSquare size={16} />} onClick={() => navigate('/chat')}>
          Chat with AI
        </Button>
        <Button variant="secondary" size="md" icon={<User size={16} />} onClick={() => navigate('/twin')}>
          View Digital Twin
        </Button>
        <Button variant="secondary" size="md" icon={<Shield size={16} />} onClick={() => navigate('/assessments')}>
          Run Health Check
        </Button>
      </div>

      <AssessmentCard />
    </div>
  );
}
