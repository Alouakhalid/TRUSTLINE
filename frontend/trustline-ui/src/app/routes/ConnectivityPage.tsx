import { useState, useEffect } from 'react';
import { Wifi, RefreshCw, Activity, ShieldCheck, Database, Globe, Server } from 'lucide-react';
import { Card, CardHeader, CardContent } from '@/shared/components/Card';
import { StatusDot } from '@/shared/components/StatusDot';
import { Button } from '@/shared/components/Button';
import { api } from '@/shared/lib/api-client';

export default function ConnectivityPage() {
  const [connectivity, setConnectivity] = useState<Record<string, unknown> | null>(null);
  const [loading, setLoading] = useState(true);

  const refresh = async () => {
    setLoading(true);
    try {
      const data = await api.getConnectivity();
      setConnectivity(data);
    } catch {
      /* ignore */
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    refresh();
    const interval = setInterval(refresh, 15000);
    return () => clearInterval(interval);
  }, []);

  const probeStatus = (val: unknown): 'nominal' | 'critical' | 'unknown' => {
    const s = typeof val === 'object' && val !== null && 'status' in val ? (val as Record<string, unknown>).status : val;
    if (s === true || s === 'ok' || s === 'OK' || s === 'reachable') return 'nominal';
    if (s === false || s === 'unreachable' || s === 'UNREACHABLE' || s === 'error' || s === 'DOWN') return 'critical';
    return 'unknown';
  };

  const probeLabel = (val: unknown): string => {
    if (typeof val === 'object' && val !== null && 'status' in val) {
      return String((val as Record<string, unknown>).status || 'OK').toUpperCase();
    }
    return String(val === true ? 'ONLINE' : val === false ? 'UNREACHABLE' : val).toUpperCase();
  };

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: '24px' }}>
      <div className="portal-header" style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', flexWrap: 'wrap', gap: '12px' }}>
        <div>
          <div style={{ display: 'flex', alignItems: 'center', gap: '8px', marginBottom: '6px' }}>
            <span className="dot-indicator dot-teal" />
            <span className="dark-label">[ NETWORK // TELEMETRY & LINK PROBES // EXP-72 ]</span>
          </div>
          <h1>Independent System Connectivity Probes</h1>
          <p>8-channel heartbeat monitoring: Database, Local AI, Cloud AI, Ground Link, DNS, Network, Sync & WebSocket</p>
        </div>
        <Button variant="secondary" size="sm" onClick={refresh} isLoading={loading} icon={<RefreshCw size={14} />}>
          Refresh Probes
        </Button>
      </div>

      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(280px, 1fr))', gap: '16px' }}>
        {connectivity &&
          Object.entries(connectivity)
            .filter(([k]) => !['timestamp', 'is_demo', 'checked_at', 'summary', 'state_transition_recorded'].includes(k))
            .map(([probe, val]) => (
              <Card key={probe} className="deck-card">
                <CardContent>
                  <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                    <div style={{ fontSize: '14px', fontWeight: 600, textTransform: 'capitalize', color: 'var(--color-ink)' }}>
                      {probe.replace(/_/g, ' ')}
                    </div>
                    <StatusDot
                      status={probeStatus(val)}
                      label={probeLabel(val)}
                      pulse={probeStatus(val) === 'nominal'}
                    />
                  </div>
                  <div className="dark-label" style={{ marginTop: '10px', fontSize: '9.5px' }}>
                    CHANNEL VERIFICATION: {probe.toUpperCase()}
                  </div>
                </CardContent>
              </Card>
            ))}
      </div>
    </div>
  );
}
