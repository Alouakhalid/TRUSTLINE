import { useState, useEffect, useRef, useId, useMemo } from 'react';

interface OscilloscopeProps {
  data?: number[];
  color?: string;
  height?: number;
  className?: string;
  label?: string;
  unit?: string;
  variant?: 'ecg' | 'respiration';
}

// Calibrated physiological Lead-II ECG waveform synthesis (P-Q-R-S-T complex)
function getEcgSample(tick: number): number {
  const cycle = tick % 24;
  if (cycle === 3) return 0.16;   // P wave
  if (cycle === 4) return 0.26;
  if (cycle === 5) return 0.14;
  if (cycle === 9) return -0.18;  // Q wave
  if (cycle === 10) return 1.62;  // R peak spike
  if (cycle === 11) return -0.52; // S wave
  if (cycle === 15) return 0.22;  // T wave
  if (cycle === 16) return 0.38;
  if (cycle === 17) return 0.24;
  return Math.sin(tick * 0.15) * 0.025; // Isoelectric baseline with subtle micro-drift
}

// Realistic thoracic impedance respiration curve
function getRespSample(tick: number): number {
  // Asymmetric sinusoidal respiratory tidal volume
  return Math.sin(tick * 0.08) * 0.85 + Math.cos(tick * 0.02) * 0.08;
}

export function Oscilloscope({
  data,
  color = '#2E6B72',
  height = 150,
  className = '',
  label,
  unit,
  variant,
}: OscilloscopeProps) {
  const gradId = useId().replace(/:/g, '');
  const isResp = variant === 'respiration' || label?.toLowerCase().includes('impedance') || color === '#E8913C';

  // Rolling 150-sample buffer
  const [buffer, setBuffer] = useState<number[]>(() => {
    if (data && data.length >= 10) {
      return [...data.slice(-150)];
    }
    return Array.from({ length: 150 }, (_, i) => (isResp ? getRespSample(i) : getEcgSample(i)));
  });

  const tickRef = useRef(150);
  const dataRef = useRef(data);
  dataRef.current = data;

  // Real-time continuous sweep at 30 FPS (~33ms)
  useEffect(() => {
    const timer = setInterval(() => {
      tickRef.current += 1;
      const currentTick = tickRef.current;
      const externalData = dataRef.current;

      // If external data is supplied and has recent points, take next sample or synthesize
      let nextVal: number;
      if (externalData && externalData.length > 0) {
        const idx = currentTick % externalData.length;
        nextVal = externalData[idx];
      } else {
        nextVal = isResp ? getRespSample(currentTick) : getEcgSample(currentTick);
      }

      setBuffer((prev) => {
        const next = prev.length >= 150 ? [...prev.slice(1), nextVal] : [...prev, nextVal];
        return next;
      });
    }, 35);

    return () => clearInterval(timer);
  }, [isResp]);

  // If props.data changes significantly, merge into buffer
  useEffect(() => {
    if (data && data.length >= 10) {
      setBuffer((prev) => {
        const fresh = data.slice(-150);
        return fresh.length >= 20 ? fresh : prev;
      });
    }
  }, [data]);

  // Compute SVG Path points and bounds
  const { pathD, areaD, headX, headY, currentDisplayVal, minVal, maxVal } = useMemo(() => {
    const pts = buffer.length > 0 ? buffer : [0, 0];
    let min = Math.min(...pts);
    let max = Math.max(...pts);
    if (max - min < 0.2) {
      min -= 0.5;
      max += 0.5;
    }
    const range = max - min;
    const w = 600;
    const h = 150;
    const paddingY = 16;
    const plotHeight = h - paddingY * 2;

    const coords = pts.map((val, i) => {
      const x = (i / (pts.length - 1)) * w;
      const norm = (val - min) / range;
      const y = h - paddingY - norm * plotHeight;
      return { x, y };
    });

    const d = coords.map((pt, i) => `${i === 0 ? 'M' : 'L'} ${pt.x.toFixed(1)},${pt.y.toFixed(1)}`).join(' ');
    const area = `${d} L ${w},${h} L 0,${h} Z`;

    const last = coords[coords.length - 1] || { x: w, y: h / 2 };
    const latestRaw = pts[pts.length - 1] ?? 0;
    const displayVal = (latestRaw >= 0 ? '+' : '') + latestRaw.toFixed(2);

    return {
      pathD: d,
      areaD: area,
      headX: last.x,
      headY: last.y,
      currentDisplayVal: displayVal,
      minVal: min.toFixed(2),
      maxVal: max.toFixed(2),
    };
  }, [buffer]);

  const defaultUnit = unit || (isResp ? 'ΔΩ' : 'mV');

  return (
    <div
      className={className}
      style={{
        position: 'relative',
        width: '100%',
        height,
        background: '#0A0C0E',
        borderRadius: 'var(--radius-xs)',
        border: '1px solid var(--color-hairline)',
        overflow: 'hidden',
        boxShadow: 'inset 0 0 20px rgba(0, 0, 0, 0.65)',
      }}
    >
      {/* Reticle & Metric HUD Overlays */}
      <div
        style={{
          position: 'absolute',
          top: 8,
          left: 10,
          right: 10,
          display: 'flex',
          justifyContent: 'space-between',
          alignItems: 'center',
          pointerEvents: 'none',
          zIndex: 2,
        }}
      >
        <div style={{ display: 'flex', alignItems: 'center', gap: '6px' }}>
          <span
            style={{
              width: '6px',
              height: '6px',
              borderRadius: '50%',
              background: color,
              boxShadow: `0 0 6px ${color}`,
            }}
          />
          <span
            className="dark-label"
            style={{
              fontSize: '10px',
              color: 'var(--color-ink)',
              letterSpacing: '0.08em',
              fontWeight: 600,
            }}
          >
            {label || (isResp ? 'THORACIC RESPIRATION' : 'LEAD-II ECG')}
          </span>
        </div>

        <div style={{ display: 'flex', alignItems: 'baseline', gap: '4px', fontFamily: 'var(--font-mono)' }}>
          <span
            style={{
              fontSize: '14px',
              fontWeight: 700,
              color,
              fontVariantNumeric: 'tabular-nums',
            }}
          >
            {currentDisplayVal}
          </span>
          <span style={{ fontSize: '10px', color: 'var(--color-muted)' }}>
            {defaultUnit}
          </span>
        </div>
      </div>

      {/* Bottom Scale & Calibrated Sweep Specs */}
      <div
        style={{
          position: 'absolute',
          bottom: 6,
          left: 10,
          right: 10,
          display: 'flex',
          justifyContent: 'space-between',
          alignItems: 'center',
          pointerEvents: 'none',
          zIndex: 2,
          fontFamily: 'var(--font-mono)',
          fontSize: '9.5px',
          color: 'var(--color-muted)',
        }}
      >
        <span>
          CAL {isResp ? '1.0 ΔΩ' : '1.0 mV'} · 25 mm/s · {isResp ? '50 Hz' : '250 Hz'}
        </span>
        <span style={{ color }}>
          ● LIVE SWEEP ACTIVE
        </span>
      </div>

      {/* Pure SVG Oscilloscope Waveform Vector */}
      <svg
        viewBox="0 0 600 150"
        preserveAspectRatio="none"
        style={{
          width: '100%',
          height: '100%',
          display: 'block',
        }}
      >
        <defs>
          <linearGradient id={`grad-${gradId}`} x1="0" y1="0" x2="0" y2="1">
            <stop offset="0%" stopColor={color} stopOpacity="0.22" />
            <stop offset="70%" stopColor={color} stopOpacity="0.05" />
            <stop offset="100%" stopColor={color} stopOpacity="0.0" />
          </linearGradient>

          {/* Calibrated fine grid pattern */}
          <pattern id={`grid-${gradId}`} width="25" height="25" patternUnits="userSpaceOnUse">
            <path d="M 25 0 L 0 0 0 25" fill="none" stroke="rgba(237, 231, 220, 0.05)" strokeWidth="0.5" />
          </pattern>
        </defs>

        {/* Oscilloscope Grid Background */}
        <rect width="600" height="150" fill={`url(#grid-${gradId})`} />

        {/* Major Reticle Dividers */}
        <line x1="0" y1="37.5" x2="600" y2="37.5" stroke="rgba(237, 231, 220, 0.08)" strokeWidth="0.7" />
        <line x1="0" y1="75" x2="600" y2="75" stroke="rgba(237, 231, 220, 0.16)" strokeWidth="0.9" strokeDasharray="4 4" />
        <line x1="0" y1="112.5" x2="600" y2="112.5" stroke="rgba(237, 231, 220, 0.08)" strokeWidth="0.7" />

        <line x1="150" y1="0" x2="150" y2="150" stroke="rgba(237, 231, 220, 0.07)" strokeWidth="0.6" />
        <line x1="300" y1="0" x2="300" y2="150" stroke="rgba(237, 231, 220, 0.09)" strokeWidth="0.8" strokeDasharray="2 4" />
        <line x1="450" y1="0" x2="450" y2="150" stroke="rgba(237, 231, 220, 0.07)" strokeWidth="0.6" />

        {/* Translucent Area Glow Under Curve */}
        <path d={areaD} fill={`url(#grad-${gradId})`} />

        {/* Crisp Vector Waveform Trace */}
        <path
          d={pathD}
          fill="none"
          stroke={color}
          strokeWidth="2.4"
          strokeLinecap="round"
          strokeLinejoin="round"
        />

        {/* Leading Phosphor Sweep Head */}
        <circle cx={headX} cy={headY} r="7" fill={color} opacity="0.3" />
        <circle cx={headX} cy={headY} r="3.5" fill={color} />
        <circle cx={headX} cy={headY} r="1.5" fill="#EDE7DC" />
      </svg>
    </div>
  );
}
