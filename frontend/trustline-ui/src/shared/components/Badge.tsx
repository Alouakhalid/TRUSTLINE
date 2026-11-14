import React from 'react';

interface BadgeProps {
  children: React.ReactNode;
  variant?: 'default' | 'success' | 'warning' | 'danger' | 'info' | 'outline';
  size?: 'sm' | 'md';
  className?: string;
  style?: React.CSSProperties;
}

export function Badge({ children, variant = 'default', size = 'sm', className = '', style }: BadgeProps) {
  return (
    <span className={`badge badge--${variant} badge--${size} ${className}`} style={style}>
      {children}
    </span>
  );
}
