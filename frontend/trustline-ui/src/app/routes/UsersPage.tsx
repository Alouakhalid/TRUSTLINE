import { useState, useEffect } from 'react';
import { Users, UserPlus, Shield } from 'lucide-react';
import { Card, CardHeader, CardContent } from '@/shared/components/Card';
import { Badge } from '@/shared/components/Badge';
import { api } from '@/shared/lib/api-client';

export default function UsersPage() {
  const [users, setUsers] = useState<Array<Record<string, unknown>>>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    api.getUsers()
      .then((data) => setUsers(data))
      .catch(() => setUsers([]))
      .finally(() => setLoading(false));
  }, []);

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: '24px' }}>
      <div className="portal-header">
        <div style={{ display: 'flex', alignItems: 'center', gap: '8px', marginBottom: '6px' }}>
          <span className="dot-indicator dot-teal" />
          <span className="dark-label">[ RBAC // ACCESS CONTROL & CREW DIRECTORY // EXP-72 ]</span>
        </div>
        <h1>User & Role Administration</h1>
        <p>Active flight crew credentials, RBAC security privileges, and astronaut bindings</p>
      </div>

      <Card className="deck-card">
        <CardHeader>
          <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
            <span className="dot-indicator dot-bone" />
            <h3 style={{ fontSize: '14px', fontWeight: 600, display: 'flex', alignItems: 'center', gap: '8px', color: 'var(--color-ink)' }}>
              <Users size={16} style={{ color: 'var(--color-teal)' }} /> Registered Users ({users.length})
            </h3>
          </div>
        </CardHeader>
        <CardContent>
          {loading ? (
            <p style={{ fontSize: '13px', color: 'var(--color-muted)' }}>Loading users...</p>
          ) : users.length === 0 ? (
            <p style={{ fontSize: '13px', color: 'var(--color-muted)' }}>No users found</p>
          ) : (
            <div style={{ overflowX: 'auto' }}>
              <table style={{ width: '100%', fontSize: '13px', borderCollapse: 'collapse' }}>
                <thead>
                  <tr style={{ borderBottom: '1px solid var(--color-hairline)' }}>
                    <th className="dark-label" style={{ textAlign: 'left', padding: '10px 12px' }}>User ID</th>
                    <th className="dark-label" style={{ textAlign: 'left', padding: '10px 12px' }}>Username</th>
                    <th className="dark-label" style={{ textAlign: 'left', padding: '10px 12px' }}>Role</th>
                    <th className="dark-label" style={{ textAlign: 'left', padding: '10px 12px' }}>Astronaut Tag</th>
                  </tr>
                </thead>
                <tbody>
                  {users.map((u, i) => (
                    <tr key={i} style={{ borderBottom: '1px solid var(--color-hairline)' }}>
                      <td style={{ padding: '12px', fontFamily: 'var(--font-mono)', fontSize: '12px', color: 'var(--color-ink-secondary)' }}>{String(u.id || `USR-${i}`)}</td>
                      <td style={{ padding: '12px', fontWeight: 600, color: 'var(--color-ink)' }}>{String(u.username)}</td>
                      <td style={{ padding: '12px' }}>
                        <Badge
                          variant={u.role === 'ADMINISTRATOR' ? 'warning' : u.role === 'MEDICAL_OFFICER' ? 'success' : 'outline'}
                          size="sm"
                        >
                          <span className={`dot-indicator ${u.role === 'ADMINISTRATOR' ? 'dot-amber' : u.role === 'MEDICAL_OFFICER' ? 'dot-teal' : 'dot-bone'}`} style={{ marginRight: '4px' }} />
                          {String(u.role)}
                        </Badge>
                      </td>
                      <td style={{ padding: '12px', fontFamily: 'var(--font-mono)', color: 'var(--color-ink-secondary)' }}>
                        {String(u.astronaut_id || '—')}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </CardContent>
      </Card>
    </div>
  );
}
