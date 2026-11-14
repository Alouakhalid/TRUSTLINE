import { useState, useEffect } from 'react';
import { RefreshCw, CheckCircle, Clock, AlertTriangle, ArrowUpRight } from 'lucide-react';
import { Card, CardHeader, CardContent } from '@/shared/components/Card';
import { Badge } from '@/shared/components/Badge';
import { Button } from '@/shared/components/Button';
import { api } from '@/shared/lib/api-client';

export default function SyncPage() {
  const [syncStatus, setSyncStatus] = useState<{ counts: Record<string, number>; is_demo: boolean } | null>(null);
  const [isRunning, setIsRunning] = useState(false);
  const [msg, setMsg] = useState('');

  const load = async () => {
    try {
      const data = await api.getSyncStatus();
      setSyncStatus(data);
    } catch {
      /* ignore */
    }
  };

  useEffect(() => {
    load();
  }, []);

  const handleRunSync = async () => {
    setIsRunning(true);
    setMsg('Executing ground synchronization batch with backoff...');
    try {
      const res = await api.runSync();
      setMsg(`Sync executed: ${JSON.stringify(res)}`);
      await load();
    } catch (err) {
      setMsg(`Sync error: ${err instanceof Error ? err.message : 'Failed'}`);
    } finally {
      setIsRunning(false);
    }
  };

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: '24px' }}>
      <div className="portal-header" style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', flexWrap: 'wrap', gap: '12px' }}>
        <div>
          <div style={{ display: 'flex', alignItems: 'center', gap: '8px', marginBottom: '6px' }}>
            <span className="dot-indicator dot-teal" />
            <span className="dark-label">[ TELEMETRY SYNC // TRANSACTIONAL OUTBOX // EXP-72 ]</span>
          </div>
          <h1>Offline Ground Synchronization Outbox</h1>
          <p>Transactional outbox queue with exponential backoff and conflict-free ground transport</p>
        </div>
        <Button variant="primary" size="md" onClick={handleRunSync} isLoading={isRunning} icon={<RefreshCw size={16} />}>
          Run Sync Dispatch
        </Button>
      </div>

      {msg && (
        <div style={{ padding: '12px 14px', background: 'var(--color-ground-secondary)', borderRadius: 'var(--radius-xs)', border: '1px solid var(--color-hairline)', fontSize: '12px', fontFamily: 'var(--font-mono)', color: 'var(--color-teal)' }}>
          {msg}
        </div>
      )}

      {/* Counts Grid */}
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(220px, 1fr))', gap: '16px' }}>
        {syncStatus &&
          Object.entries(syncStatus.counts || {}).map(([state, count]) => (
            <Card key={state} className="deck-card">
              <CardContent>
                <div className="dark-label">
                  {state} RECORDS
                </div>
                <div style={{ fontSize: '34px', fontWeight: 700, fontFamily: 'var(--font-display)', fontVariantNumeric: 'tabular-nums', marginTop: '6px', color: 'var(--color-ink)' }}>
                  {count}
                </div>
                <div style={{ marginTop: '10px' }}>
                  <Badge variant={state === 'DELIVERED' ? 'success' : state === 'PENDING' ? 'warning' : 'outline'} size="sm">
                    <span className={`dot-indicator ${state === 'DELIVERED' ? 'dot-teal' : state === 'PENDING' ? 'dot-amber' : 'dot-bone'}`} style={{ marginRight: '4px' }} />
                    {state}
                  </Badge>
                </div>
              </CardContent>
            </Card>
          ))}
      </div>
    </div>
  );
}
