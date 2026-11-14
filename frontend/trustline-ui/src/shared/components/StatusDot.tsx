interface StatusDotProps {
  status: 'nominal' | 'warning' | 'critical' | 'offline' | 'unknown';
  label?: string;
  pulse?: boolean;
  className?: string;
}

export function StatusDot({ status, label, pulse = false, className = '' }: StatusDotProps) {
  return (
    <span className={`status-indicator ${className}`} role="status" aria-label={label || status}>
      <span className={`status-dot status-dot--${status} ${pulse ? 'status-dot--pulse' : ''}`} aria-hidden="true" />
      {label && <span className="status-label">{label}</span>}
    </span>
  );
}
