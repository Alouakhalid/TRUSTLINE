import { useState, useEffect } from 'react';
import { Brain, Layers, Tag, ShieldCheck } from 'lucide-react';
import { Card, CardHeader, CardContent } from '@/shared/components/Card';
import { Badge } from '@/shared/components/Badge';
import { useAuth } from '@/features/auth';
import { api } from '@/shared/lib/api-client';

const NAMESPACES = ['PHA', 'SQA', 'RAA', 'MEDICAL_RAG'] as const;

export default function MemoryPage() {
  const { astronautId } = useAuth();
  const [activeNamespace, setActiveNamespace] = useState<string>('PHA');
  const [memories, setMemories] = useState<Array<Record<string, unknown>>>([]);
  const [isLoading, setIsLoading] = useState(false);

  useEffect(() => {
    async function load() {
      setIsLoading(true);
      try {
        const data = await api.getMemories(astronautId || 'UNASSIGNED', activeNamespace);
        setMemories(data);
      } catch {
        setMemories([]);
      } finally {
        setIsLoading(false);
      }
    }
    load();
  }, [astronautId, activeNamespace]);

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: '24px' }}>
      <div className="portal-header">
        <div style={{ display: 'flex', alignItems: 'center', gap: '8px', marginBottom: '6px' }}>
          <span className="dot-indicator dot-teal" />
          <span className="dark-label">[ MEMORY // AUDITABLE AGENT STATE // EXP-72 ]</span>
        </div>
        <h1>Agent Short-Term & Long-Term Memory Governance</h1>
        <p>Auditable, versioned clinical memory items partitioned by agent namespace</p>
      </div>

      {/* Namespace Tabs */}
      <div style={{ display: 'flex', gap: '8px', flexWrap: 'wrap' }}>
        {NAMESPACES.map((ns) => (
          <button
            key={ns}
            type="button"
            className={`badge badge--md ${activeNamespace === ns ? 'badge--info' : 'badge--outline'}`}
            onClick={() => setActiveNamespace(ns)}
            style={{ cursor: 'pointer', padding: '8px 16px', fontSize: '12px' }}
          >
            <span className={`dot-indicator ${activeNamespace === ns ? 'dot-teal' : 'dot-bone'}`} style={{ marginRight: '6px' }} />
            {ns} Namespace
          </button>
        ))}
      </div>

      <Card className="deck-card">
        <CardHeader>
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
            <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
              <span className="dot-indicator dot-teal" />
              <h3 style={{ fontSize: '14px', fontWeight: 600, display: 'flex', alignItems: 'center', gap: '8px', color: 'var(--color-ink)' }}>
                <Brain size={16} style={{ color: 'var(--color-teal)' }} /> Memory Records — {activeNamespace} ({memories.length})
              </h3>
            </div>
            <Badge variant="outline" size="sm">
              <span className="dark-label" style={{ fontSize: '10px' }}>CREW {astronautId || 'AST-001'}</span>
            </Badge>
          </div>
        </CardHeader>
        <CardContent>
          {isLoading ? (
            <p style={{ fontSize: '13px', color: 'var(--color-muted)' }}>Loading memories...</p>
          ) : memories.length === 0 ? (
            <div style={{ padding: '36px 16px', textAlign: 'center', color: 'var(--color-muted)' }}>
              <p style={{ fontSize: '14px', fontWeight: 500, color: 'var(--color-ink)' }}>No memory records stored in {activeNamespace}</p>
              <p className="dark-label" style={{ marginTop: '6px' }}>
                MEMORIES ARE DYNAMICALLY COMMITTED DURING MULTI-AGENT DIAGNOSTIC ASSESSMENTS
              </p>
            </div>
          ) : (
            <div style={{ display: 'flex', flexDirection: 'column', gap: '10px' }}>
              {memories.map((m, idx) => (
                <div
                  key={idx}
                  style={{
                    padding: '14px 16px',
                    borderRadius: 'var(--radius-xs)',
                    background: 'var(--color-ground-secondary)',
                    border: '1px solid var(--color-hairline)',
                  }}
                >
                  <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '8px' }}>
                    <div style={{ fontSize: '12px', fontFamily: 'var(--font-mono)', fontWeight: 600, color: 'var(--color-ink)' }}>
                      KEY: {String(m.memory_key || m.id || idx)}
                    </div>
                    <div style={{ display: 'flex', gap: '6px', alignItems: 'center' }}>
                      <Badge variant="success" size="sm">
                        <span className="dot-indicator dot-teal" style={{ marginRight: '4px' }} />
                        v{String(m.version || '1')}
                      </Badge>
                      <Badge variant="info" size="sm">
                        {String(m.status || 'LIVE')}
                      </Badge>
                    </div>
                  </div>
                  <div style={{ fontSize: '13px', color: 'var(--color-ink-secondary)', fontFamily: 'var(--font-mono)' }}>
                    {typeof m.content === 'string' ? m.content : JSON.stringify(m.content)}
                  </div>
                </div>
              ))}
            </div>
          )}
        </CardContent>
      </Card>
    </div>
  );
}
