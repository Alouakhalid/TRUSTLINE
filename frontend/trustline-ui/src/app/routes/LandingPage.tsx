import { useRef } from 'react';
import { Link } from 'react-router-dom';
import { Activity, HeartPulse, ShieldAlert, BookOpen, Cpu, Cloud, GitBranch, Satellite, ChevronRight } from 'lucide-react';
import { Button } from '@/shared/components/Button';
import gsap from 'gsap';
import { useGSAP } from '@gsap/react';
import { ScrollTrigger } from 'gsap/ScrollTrigger';

gsap.registerPlugin(useGSAP, ScrollTrigger);

const AGENTS = [
  {
    icon: Activity,
    code: 'SQA-01',
    title: 'Sensor Quality Agent',
    desc: 'Real-time signal integrity, sensor drift detection, channel quarantine, and anomaly tagging across 10 physiological sensors.',
    accent: 'teal',
  },
  {
    icon: HeartPulse,
    code: 'PHA-02',
    title: 'Personal Health Agent',
    desc: 'Vital signs processing, symptom evaluation, Isolation Forest anomaly scoring, and medical document intelligence.',
    accent: 'amber',
  },
  {
    icon: ShieldAlert,
    code: 'RAA-03',
    title: 'Risk Assessment Agent',
    desc: 'Multi-domain clinical risk quantification across 10 NASA-STD-3001 aerospace medical domains with escalation protocol.',
    accent: 'teal',
  },
  {
    icon: BookOpen,
    code: 'RAG-04',
    title: 'Medical RAG Protocol',
    desc: 'Contextual search over aerospace clinical flight rules with citation grounding and guideline contradiction detection.',
    accent: 'amber',
  },
];

const MODES = [
  {
    icon: Cpu,
    title: 'LOCAL Mode',
    desc: 'Spacecraft edge inference via local Ollama runtime. Complete operational autonomy during communications blackout.',
    tag: 'OFFLINE // PRIMARY',
    accent: 'teal',
  },
  {
    icon: Cloud,
    title: 'CLOUD Mode',
    desc: 'High-capability ground station inference via Groq for complex differential synthesis and flight surgeon briefings.',
    tag: 'GROUND // STANDBY',
    accent: 'amber',
  },
  {
    icon: GitBranch,
    title: 'HYBRID Mode',
    desc: 'Autonomous dynamic routing with deterministic circuit breaker. Instant zero-loss fallback on link loss.',
    tag: 'DYNAMIC // FAULT-TOLERANT',
    accent: 'teal',
  },
];

export default function LandingPage() {
  const containerRef = useRef<HTMLDivElement>(null);

  useGSAP(() => {
    const mm = gsap.matchMedia();
    mm.add('(prefers-reduced-motion: no-preference)', () => {
      gsap.from('.hero-label-badge', { opacity: 0, y: 20, duration: 0.6, ease: 'power2.out' });
      gsap.from('.landing-hero h1', { opacity: 0, y: 30, duration: 0.8, delay: 0.1, ease: 'power3.out' });
      gsap.from('.landing-hero p', { opacity: 0, y: 20, duration: 0.6, delay: 0.2, ease: 'power2.out' });
      gsap.from('.landing-cta', { opacity: 0, y: 15, duration: 0.5, delay: 0.3, ease: 'power2.out' });
      gsap.from('.hero-deck-card', { opacity: 0, y: 40, duration: 0.9, delay: 0.4, ease: 'power3.out' });

      ScrollTrigger.batch('.landing-card', {
        onEnter: (batch) => {
          gsap.to(batch, { opacity: 1, y: 0, stagger: 0.08, duration: 0.5, ease: 'power2.out' });
        },
        start: 'top 85%',
      });
      gsap.set('.landing-card', { opacity: 0, y: 24 });
    });
  }, { scope: containerRef });

  return (
    <div ref={containerRef} className="landing-root">
      {/* Hero Section */}
      <section className="landing-hero">
        <div className="hero-label-badge" style={{ display: 'inline-flex', alignItems: 'center', gap: '8px', marginBottom: '20px' }}>
          <span className="dot-indicator dot-teal" />
          <span className="dark-label">MISSION STATUS // AUTONOMOUS SPACE HEALTH // EXP-72</span>
          <span className="dot-indicator dot-amber" />
        </div>

        <h1>Autonomous Space Health Intelligence</h1>
        <p>
          Protecting astronaut health during deep space missions with AI-powered diagnostics,
          real-time telemetry validation, and an offline-first architecture designed for zero-connectivity deep space operations.
        </p>

        <div className="landing-cta">
          <Link to="/portal">
            <Button variant="primary" size="lg">
              Get Started <ChevronRight size={16} style={{ marginLeft: '4px' }} />
            </Button>
          </Link>
          <Link to="/portal">
            <Button variant="secondary" size="lg">Enter Mission Control</Button>
          </Link>
        </div>

        {/* Hero Deck Card with Authentic Photography */}
        <div className="hero-deck-card">
          <div className="hero-deck-card-bar">
            <div style={{ display: 'flex', alignItems: 'center', gap: '10px' }}>
              <span className="dot-indicator dot-teal" />
              <span className="dark-label" style={{ color: 'var(--color-ink)' }}>FIGURE 01.1 // EVA EXTRAVEHICULAR SUIT TELEMETRY HARNESS</span>
            </div>
            <div style={{ display: 'flex', alignItems: 'center', gap: '12px' }}>
              <span className="dark-label">BAND-01: TEAL #2E6B72</span>
              <span className="rule-hairline" style={{ width: '1px', height: '12px', display: 'inline-block' }} />
              <span className="dark-label">BAND-02: AMBER #E8913C</span>
              <span className="dot-indicator dot-amber" />
            </div>
          </div>

          <div className="hero-deck-card-image-wrap">
            <img
              src="/assets/hero_astronaut.jpg"
              alt="Astronaut in EVA suit with visor telemetry reflections"
              loading="eager"
            />
          </div>

          <div className="hero-deck-card-bar" style={{ borderTop: '1px solid var(--color-hairline)', borderBottom: 'none' }}>
            <span className="dark-label" style={{ fontSize: '10.5px' }}>
              SOURCE: NEBUVITA DEEP SPACE PAYLOAD // LEAD-II PRECORDIAL & RESPIRATORY IMPEDANCE WINDOW
            </span>
            <span className="dark-label" style={{ color: 'var(--color-ink-secondary)', fontSize: '10.5px' }}>
              SPEC 2026 // GROUND #0A0C0E // BONE #EDE7DC
            </span>
          </div>
        </div>
      </section>

      {/* Agents Section */}
      <section className="landing-section">
        <div style={{ textAlign: 'center', marginBottom: '8px' }}>
          <span className="dark-label" style={{ color: 'var(--color-teal)' }}>[ MULTI-AGENT SUPERVISOR ]</span>
        </div>
        <h2 className="landing-section-title">Four Specialized AI Agents</h2>
        <p className="landing-section-sub">
          A LangGraph Supervisor orchestrates four domain-specific agents for continuous, auditable clinical reasoning.
        </p>

        <div className="landing-grid">
          {AGENTS.map((a) => (
            <div key={a.title} className="landing-card deck-card">
              <div className="landing-card-header">
                <div className={`landing-card-icon ${a.accent === 'amber' ? 'landing-card-icon--amber' : ''}`}>
                  <a.icon size={18} />
                </div>
                <span className="dark-label" style={{ color: a.accent === 'amber' ? 'var(--color-amber)' : 'var(--color-teal)' }}>
                  {a.code}
                </span>
              </div>
              <h3>{a.title}</h3>
              <p>{a.desc}</p>
              <div style={{ marginTop: 'auto', paddingTop: '16px' }}>
                <div className={a.accent === 'amber' ? 'rule-amber' : 'rule-teal'} style={{ width: '28px', height: '2px' }} />
              </div>
            </div>
          ))}
        </div>
      </section>

      {/* Architecture Section */}
      <section className="landing-section" style={{ borderTop: '1px solid var(--color-hairline)' }}>
        <div style={{ textAlign: 'center', marginBottom: '8px' }}>
          <span className="dark-label" style={{ color: 'var(--color-amber)' }}>[ MISSION RESILIENCE ]</span>
        </div>
        <h2 className="landing-section-title">Hybrid AI Architecture</h2>
        <p className="landing-section-sub">
          Engineered for extreme orbital delays. Operates fully autonomously in deep space and synchronizes seamlessly when ground contact is established.
        </p>

        <div className="landing-grid">
          {MODES.map((m) => (
            <div key={m.title} className="landing-card deck-card">
              <div className="landing-card-header">
                <div className={`landing-card-icon ${m.accent === 'amber' ? 'landing-card-icon--amber' : ''}`}>
                  <m.icon size={18} />
                </div>
                <span className="dot-indicator" style={{ background: m.accent === 'amber' ? 'var(--color-amber)' : 'var(--color-teal)' }} />
              </div>
              <h3>{m.title}</h3>
              <p>{m.desc}</p>
              <div style={{ marginTop: '16px', display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
                <span className="badge badge--default badge--sm">
                  {m.tag}
                </span>
              </div>
            </div>
          ))}
        </div>
      </section>

      {/* Footer */}
      <footer className="landing-footer">
        <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'center', gap: '8px', marginBottom: '8px' }}>
          <Satellite size={15} style={{ color: 'var(--color-teal)' }} />
          <strong style={{ fontFamily: 'var(--font-display)', letterSpacing: '-0.02em', color: 'var(--color-ink)' }}>
            TRUSTLINE
          </strong>
          <span style={{ color: 'var(--color-muted)' }}>// NEBUVITA AEROSPACE</span>
        </div>
        <p className="dark-label" style={{ fontSize: '10.5px' }}>
          NASA Artemis Deep Space Health Initiative • Ground #0A0C0E • Bone #EDE7DC • Hairlines rgba(237,231,220,.13)
        </p>
      </footer>
    </div>
  );
}
