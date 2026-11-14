import { useState, useEffect } from 'react';
import { StatusDot } from '@/shared/components/StatusDot';
import { api } from '@/shared/lib/api-client';

export function ProviderStatus() {
  const [status, setStatus] = useState<'nominal' | 'critical' | 'unknown'>('unknown');
  const [label, setLabel] = useState('Checking...');

  useEffect(() => {
    async function check() {
      try {
        const health = await api.getHealth();
        if (health.status === 'ok') {
          setStatus('nominal');
          setLabel('API Connected');
        } else {
          setStatus('critical');
          setLabel('API Error');
        }
      } catch {
        setStatus('critical');
        setLabel('API Offline');
      }
    }
    check();
    const id = setInterval(check, 30000);
    return () => clearInterval(id);
  }, []);

  return <StatusDot status={status} label={label} pulse={status === 'nominal'} />;
}
