import { useState, useEffect } from 'react';
import { ScrollText, Filter } from 'lucide-react';
import { Card, CardHeader, CardContent } from '@/shared/components/Card';
import { Badge } from '@/shared/components/Badge';
import { api } from '@/shared/lib/api-client';

export default function AuditPage() {
  const [logs, setLogs] = useState<Array<Record<string, unknown>>>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    api.getAuditLogs(100)
      .then((data) => setLogs(data))
      .catch(() => setLogs([]))
      .finally(() => setLoading(false));
  }, []);

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: '24px' }}>
      <div className="portal-header">
        <div style={{ display: 'flex', alignItems: 'center', gap: '8px', marginBottom: '6px' }}>
          <span className="dot-indicator dot-teal" />
          <span className="dark-label">[ FORENSICS // IMMUTABLE AUDIT TRAIL // EXP-72 ]</span>
        </div>
        <h1>Mission Security & Audit Trails</h1>
        <p>Immutable forensic record of all clinical decisions, auth events, and data transfers</p>
      </div>

      <Card className="deck-card">
        <CardHeader>
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
            <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
              <span className="dot-indicator dot-bone" />
              <h3 style={{ fontSize: '14px', fontWeight: 600, display: 'flex', alignItems: 'center', gap: '8px', color: 'var(--color-ink)' }}>
                <ScrollText size={16} style={{ color: 'var(--color-teal)' }} /> Audit Trail ({logs.length} events)
              </h3>
            </div>
            <Badge variant="outline" size="sm">
              <span className="dot-indicator dot-teal" style={{ marginRight: '4px' }} />
              IMMUTABLE
            </Badge>
          </div>
        </CardHeader>
        <CardContent>
          {loading ? (
            <p style={{ fontSize: '13px', color: 'var(--color-muted)' }}>Loading audit records...</p>
          ) : logs.length === 0 ? (
            <p style={{ fontSize: '13px', color: 'var(--color-muted)' }}>No audit events found</p>
          ) : (
            <div style={{ display: 'flex', flexDirection: 'column', gap: '8px', maxHeight: '500px', overflowY: 'auto' }}>
              {logs.map((log, idx) => (
                <div
                  key={idx}
                  style={{
                    display: 'flex',
                    justifyContent: 'space-between',
                    alignItems: 'center',
                    padding: '12px 14px',
                    borderRadius: 'var(--radius-xs)',
                    background: 'var(--color-ground-secondary)',
                    border: '1px solid var(--color-hairline)',
                    fontSize: '12px',
                  }}
                >
                  <div style={{ display: 'flex', alignItems: 'center', gap: '10px' }}>
                    <Badge variant="outline" size="sm">
                      <span className="dot-indicator dot-teal" style={{ marginRight: '4px' }} />
                      {String(log.action)}
                    </Badge>
                    <span style={{ fontWeight: 600, color: 'var(--color-ink)' }}>{String(log.resource_type)}</span>
                    <span style={{ color: 'var(--color-ink-secondary)', fontFamily: 'var(--font-mono)' }}>
                      {String(log.resource_id || '')}
                    </span>
                  </div>
                  <span style={{ color: 'var(--color-muted)', fontFamily: 'var(--font-mono)', fontSize: '11px' }}>
                    {log.created_at ? new Date(String(log.created_at)).toLocaleString() : ''}
                  </span>
                </div>
              ))}
            </div>
          )}
        </CardContent>
      </Card>
    </div>
  );
}
