import { useState, useEffect, useRef } from 'react';
import { Wifi, RefreshCw, Users, ScrollText } from 'lucide-react';
import { Card, CardHeader, CardContent } from '@/shared/components/Card';
import { Badge } from '@/shared/components/Badge';
import { Button } from '@/shared/components/Button';
import { StatusDot } from '@/shared/components/StatusDot';
import { Skeleton } from '@/shared/components/Skeleton';
import { api } from '@/shared/lib/api-client';
import gsap from 'gsap';
import { useGSAP } from '@gsap/react';

gsap.registerPlugin(useGSAP);

export default function AdminPortal() {
  const containerRef = useRef<HTMLDivElement>(null);
  const [connectivity, setConnectivity] = useState<Record<string, unknown> | null>(null);
  const [syncStatus, setSyncStatus] = useState<{ counts: Record<string, number> } | null>(null);
  const [users, setUsers] = useState<Array<Record<string, unknown>>>([]);
  const [auditLogs, setAuditLogs] = useState<Array<Record<string, unknown>>>([]);
  const [loading, setLoading] = useState(true);
  const [syncing, setSyncing] = useState(false);

  useEffect(() => {
    async function load() {
      try {
        const [conn, sync, usr, audit] = await Promise.all([
          api.getConnectivity().catch(() => null),
          api.getSyncStatus().catch(() => null),
          api.getUsers().catch(() => []),
          api.getAuditLogs(20).catch(() => []),
        ]);
        setConnectivity(conn);
        setSyncStatus(sync);
        setUsers(usr);
        setAuditLogs(audit);
      } finally {
        setLoading(false);
      }
    }
    load();
  }, []);

  const handleSync = async () => {
    setSyncing(true);
    try {
      await api.runSync();
      const status = await api.getSyncStatus();
      setSyncStatus(status);
    } finally {
      setSyncing(false);
    }
  };

  useGSAP(() => {
    const mm = gsap.matchMedia();
    mm.add('(prefers-reduced-motion: no-preference)', () => {
      gsap.from('.card', { opacity: 0, y: 20, stagger: 0.08, duration: 0.4, ease: 'power2.out' });
    });
  }, { scope: containerRef });

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
    return String(val === true ? 'OK' : val === false ? 'DOWN' : val).toUpperCase();
  };

  return (
    <div ref={containerRef}>
      <div className="portal-header">
        <div style={{ display: 'flex', alignItems: 'center', gap: '8px', marginBottom: '6px' }}>
          <span className="dot-indicator dot-teal" />
          <span className="dark-label">[ MISSION CONTROL // SYSTEM GOVERNANCE & PROBES ]</span>
        </div>
        <h1>Mission Control Administration</h1>
        <p>System health, synchronization, and governance</p>
      </div>

      <div className="portal-grid">
        {/* Connectivity */}
        <Card className="deck-card">
          <CardHeader>
            <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
              <span className="dot-indicator dot-teal" />
              <h3 style={{ fontSize: '14px', fontWeight: 600, display: 'flex', alignItems: 'center', gap: '8px', color: 'var(--color-ink)' }}>
                <Wifi size={16} style={{ color: 'var(--color-teal)' }} /> System Connectivity
              </h3>
            </div>
          </CardHeader>
          <CardContent>
            {loading ? <Skeleton height={120} /> : connectivity ? (
              <div style={{ display: 'flex', flexDirection: 'column', gap: '10px' }}>
                {Object.entries(connectivity)
                  .filter(([k]) => !['timestamp', 'is_demo', 'checked_at', 'summary', 'state_transition_recorded'].includes(k))
                  .map(([key, val]) => (
                  <div key={key} style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
                    <span style={{ fontSize: '13px', fontFamily: 'var(--font-mono)', textTransform: 'capitalize', color: 'var(--color-ink-secondary)' }}>
                      {key.replace(/_/g, ' ')}
                    </span>
                    <StatusDot status={probeStatus(val)} label={probeLabel(val)} />
                  </div>
                ))}
              </div>
            ) : (
              <p style={{ fontSize: '13px', color: 'var(--color-muted)' }}>Failed to load connectivity data</p>
            )}
          </CardContent>
        </Card>

        {/* Sync Queue */}
        <Card className="deck-card">
          <CardHeader>
            <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
              <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
                <span className="dot-indicator dot-amber" />
                <h3 style={{ fontSize: '14px', fontWeight: 600, display: 'flex', alignItems: 'center', gap: '8px', color: 'var(--color-ink)' }}>
                  <RefreshCw size={16} style={{ color: 'var(--color-amber)' }} /> Sync Queue
                </h3>
              </div>
              <Button variant="primary" size="sm" onClick={handleSync} isLoading={syncing}>
                Run Sync
              </Button>
            </div>
          </CardHeader>
          <CardContent>
            {loading ? <Skeleton height={80} /> : syncStatus ? (
              <div style={{ display: 'flex', gap: '16px', flexWrap: 'wrap' }}>
                {Object.entries(syncStatus.counts || {}).map(([status, count]) => (
                  <div key={status} style={{ textAlign: 'center', padding: '10px 14px', background: 'var(--color-ground-secondary)', borderRadius: 'var(--radius-xs)', border: '1px solid var(--color-hairline)' }}>
                    <div style={{ fontSize: '24px', fontWeight: 700, fontFamily: 'var(--font-display)', fontVariantNumeric: 'tabular-nums', color: 'var(--color-ink)' }}>{count}</div>
                    <div className="dark-label" style={{ marginTop: '2px', fontSize: '9.5px' }}>{status}</div>
                  </div>
                ))}
              </div>
            ) : (
              <p style={{ fontSize: '13px', color: 'var(--color-muted)' }}>No sync data</p>
            )}
          </CardContent>
        </Card>

        {/* User Management */}
        <Card className="deck-card">
          <CardHeader>
            <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
              <span className="dot-indicator dot-bone" />
              <h3 style={{ fontSize: '14px', fontWeight: 600, display: 'flex', alignItems: 'center', gap: '8px', color: 'var(--color-ink)' }}>
                <Users size={16} style={{ color: 'var(--color-teal)' }} /> User Management
              </h3>
            </div>
          </CardHeader>
          <CardContent>
            {loading ? <Skeleton height={100} /> : users.length > 0 ? (
              <div style={{ overflowX: 'auto' }}>
                <table style={{ width: '100%', fontSize: '12px', borderCollapse: 'collapse' }}>
                  <thead>
                    <tr style={{ borderBottom: '1px solid var(--color-hairline)' }}>
                      <th className="dark-label" style={{ textAlign: 'left', padding: '8px' }}>Username</th>
                      <th className="dark-label" style={{ textAlign: 'left', padding: '8px' }}>Role</th>
                      <th className="dark-label" style={{ textAlign: 'left', padding: '8px' }}>Astronaut ID</th>
                    </tr>
                  </thead>
                  <tbody>
                    {users.map((u, i) => (
                      <tr key={i} style={{ borderBottom: '1px solid var(--color-hairline)' }}>
                        <td style={{ padding: '8px', fontFamily: 'var(--font-mono)', color: 'var(--color-ink)' }}>{String(u.username)}</td>
                        <td style={{ padding: '8px' }}>
                          <Badge variant={u.role === 'ADMINISTRATOR' ? 'warning' : u.role === 'MEDICAL_OFFICER' ? 'success' : 'outline'} size="sm">
                            <span className={`dot-indicator ${u.role === 'ADMINISTRATOR' ? 'dot-amber' : u.role === 'MEDICAL_OFFICER' ? 'dot-teal' : 'dot-bone'}`} style={{ marginRight: '4px' }} />
                            {String(u.role)}
                          </Badge>
                        </td>
                        <td style={{ padding: '8px', color: 'var(--color-muted)' }}>{String(u.astronaut_id || '—')}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            ) : (
              <p style={{ fontSize: '13px', color: 'var(--color-muted)' }}>No users registered</p>
            )}
          </CardContent>
        </Card>

        {/* Audit Log */}
        <Card className="deck-card">
          <CardHeader>
            <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
              <span className="dot-indicator dot-teal" />
              <h3 style={{ fontSize: '14px', fontWeight: 600, display: 'flex', alignItems: 'center', gap: '8px', color: 'var(--color-ink)' }}>
                <ScrollText size={16} style={{ color: 'var(--color-teal)' }} /> Audit Log
              </h3>
            </div>
          </CardHeader>
          <CardContent>
            {loading ? <Skeleton height={100} /> : auditLogs.length > 0 ? (
              <div style={{ display: 'flex', flexDirection: 'column', gap: '6px', maxHeight: '240px', overflowY: 'auto' }}>
                {auditLogs.map((log, i) => (
                  <div key={i} style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', padding: '8px 0', borderBottom: '1px solid var(--color-hairline)', fontSize: '12px' }}>
                    <div style={{ display: 'flex', gap: '8px', alignItems: 'center' }}>
                      <Badge variant="outline" size="sm">
                        <span className="dot-indicator dot-teal" style={{ marginRight: '4px' }} />
                        {String(log.action)}
                      </Badge>
                      <span style={{ color: 'var(--color-ink-secondary)' }}>{String(log.resource_type)}</span>
                    </div>
                    <span style={{ color: 'var(--color-muted)', fontFamily: 'var(--font-mono)', fontSize: '11px' }}>
                      {log.created_at ? new Date(String(log.created_at)).toLocaleTimeString() : ''}
                    </span>
                  </div>
                ))}
              </div>
            ) : (
              <p style={{ fontSize: '13px', color: 'var(--color-muted)' }}>No audit events</p>
            )}
          </CardContent>
        </Card>
      </div>
    </div>
  );
}
