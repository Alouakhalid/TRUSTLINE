import { useRef, useEffect, useCallback } from 'react';

interface OscilloscopeProps {
  data: number[];
  color?: string;
  height?: number;
  className?: string;
  label?: string;
}

export function Oscilloscope({ data, color = '#2E6B72', height = 140, className = '', label }: OscilloscopeProps) {
  const canvasRef = useRef<HTMLCanvasElement>(null);
  const bufferRef = useRef<number[]>([]);
  const rafRef = useRef<number>(0);

  useEffect(() => {
    if (data && data.length > 0) {
      bufferRef.current = [...data];
    }
  }, [data]);

  const draw = useCallback(() => {
    const canvas = canvasRef.current;
    if (!canvas) {
      rafRef.current = requestAnimationFrame(draw);
      return;
    }
    const ctx = canvas.getContext('2d');
    if (!ctx) {
      rafRef.current = requestAnimationFrame(draw);
      return;
    }

    // Always continue the 60fps RAF loop
    rafRef.current = requestAnimationFrame(draw);

    const w = canvas.width;
    const h = canvas.height;
    const buffer = bufferRef.current;

    /* Near-black ground */
    ctx.fillStyle = '#0A0C0E';
    ctx.fillRect(0, 0, w, h);

    /* Hairline grid lines */
    ctx.strokeStyle = 'rgba(237, 231, 220, 0.07)';
    ctx.lineWidth = 0.5;
    for (let y = 0; y <= h; y += h / 4) {
      ctx.beginPath();
      ctx.moveTo(0, y);
      ctx.lineTo(w, y);
      ctx.stroke();
    }
    for (let x = 0; x <= w; x += w / 8) {
      ctx.beginPath();
      ctx.moveTo(x, 0);
      ctx.lineTo(x, h);
      ctx.stroke();
    }

    /* Center horizontal reticle line */
    ctx.strokeStyle = 'rgba(237, 231, 220, 0.12)';
    ctx.lineWidth = 0.8;
    ctx.setLineDash([2, 4]);
    ctx.beginPath();
    ctx.moveTo(0, h / 2);
    ctx.lineTo(w, h / 2);
    ctx.stroke();
    ctx.setLineDash([]);

    if (buffer.length < 2) {
      // Draw nominal baseline flatline
      ctx.strokeStyle = color;
      ctx.lineWidth = 1.5;
      ctx.beginPath();
      ctx.moveTo(0, h / 2);
      ctx.lineTo(w, h / 2);
      ctx.stroke();
      return;
    }

    let min = Math.min(...buffer);
    let max = Math.max(...buffer);
    if (max - min < 0.2) {
      min -= 0.5;
      max += 0.5;
    }
    const range = max - min;

    /* Crisp waveform trace without glow */
    ctx.strokeStyle = color;
    ctx.lineWidth = 1.8;
    ctx.lineJoin = 'round';
    ctx.lineCap = 'round';
    ctx.beginPath();

    for (let i = 0; i < buffer.length; i++) {
      const x = (i / (buffer.length - 1)) * w;
      const y = h - ((buffer[i] - min) / range) * (h * 0.75) - h * 0.125;
      if (i === 0) ctx.moveTo(x, y);
      else ctx.lineTo(x, y);
    }
    ctx.stroke();

    // Leading sweep dot / phosphor tip
    if (buffer.length > 0) {
      const lastX = w;
      const lastY = h - ((buffer[buffer.length - 1] - min) / range) * (h * 0.75) - h * 0.125;
      ctx.fillStyle = color;
      ctx.beginPath();
      ctx.arc(lastX - 2, lastY, 3, 0, Math.PI * 2);
      ctx.fill();
    }
  }, [color]);

  useEffect(() => {
    rafRef.current = requestAnimationFrame(draw);
    return () => cancelAnimationFrame(rafRef.current);
  }, [draw]);

  return (
    <div className={className} style={{ position: 'relative' }}>
      {label && (
        <span
          className="dark-label"
          style={{
            position: 'absolute',
            top: 6,
            left: 10,
            fontSize: '9.5px',
            color: 'var(--color-muted)',
            zIndex: 1,
          }}
        >
          {label}
        </span>
      )}
      <canvas
        ref={canvasRef}
        width={600}
        height={height}
        style={{
          width: '100%',
          height,
          borderRadius: 'var(--radius-xs)',
          border: '1px solid var(--color-hairline)',
          display: 'block',
        }}
      />
    </div>
  );
}
