import { useRef } from 'react';
import { useNavigate } from 'react-router-dom';
import { HeartPulse, Droplets, Thermometer, Activity, Wind, Zap, MessageSquare, User, Shield } from 'lucide-react';
import { Card, CardContent } from '@/shared/components/Card';
import { Badge } from '@/shared/components/Badge';
import { Button } from '@/shared/components/Button';
import { useAuth } from '@/features/auth';
import { AssessmentCard } from '@/features/assessments';
import gsap from 'gsap';
import { useGSAP } from '@gsap/react';

gsap.registerPlugin(useGSAP);

const VITALS = [
  { icon: HeartPulse, label: 'Heart Rate', value: '72', unit: 'bpm', status: 'NOMINAL' },
  { icon: Droplets, label: 'SpO₂', value: '98', unit: '%', status: 'NOMINAL' },
  { icon: Thermometer, label: 'Core Temp', value: '36.8', unit: '°C', status: 'NOMINAL' },
  { icon: Activity, label: 'Blood Pressure', value: '120/80', unit: 'mmHg', status: 'NOMINAL' },
  { icon: Wind, label: 'Respiration', value: '16', unit: 'br/min', status: 'NOMINAL' },
  { icon: Zap, label: 'EDA', value: '4.2', unit: 'μS', status: 'NOMINAL' },
];

export default function AstronautPortal() {
  const { astronautId } = useAuth();
  const navigate = useNavigate();
  const containerRef = useRef<HTMLDivElement>(null);

  useGSAP(() => {
    const mm = gsap.matchMedia();
    mm.add('(prefers-reduced-motion: no-preference)', () => {
      gsap.from('.vital-card', { opacity: 0, y: 20, stagger: 0.06, duration: 0.4, ease: 'power2.out' });
    });
  }, { scope: containerRef });

  return (
    <div ref={containerRef}>
      <div className="portal-header">
        <div style={{ display: 'flex', alignItems: 'center', gap: '8px', marginBottom: '6px' }}>
          <span className="dot-indicator dot-teal" />
          <span className="dark-label">[ CREW BIOMEDICAL MANIFEST // EXP-72 ]</span>
        </div>
        <h1>Astronaut Dashboard</h1>
        <p>Crew Member {astronautId} · {new Date().toLocaleDateString('en-US', { weekday: 'long', year: 'numeric', month: 'long', day: 'numeric' })}</p>
      </div>

      <div className="portal-grid">
        {VITALS.map((v) => (
          <Card key={v.label} className="vital-card deck-card" variant="default">
            <CardContent>
              <div className="vital-icon"><v.icon size={22} style={{ color: 'var(--color-teal)' }} /></div>
              <div className="vital-value">
                {v.value}
                <span className="vital-unit">{v.unit}</span>
              </div>
              <div className="vital-label">{v.label}</div>
              <Badge variant="success" size="sm">
                <span className="dot-indicator dot-teal" style={{ marginRight: '4px' }} />
                {v.status}
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
