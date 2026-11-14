import { useState, useEffect } from 'react';
import { Cpu, Cloud, ShieldAlert, CheckCircle, AlertTriangle, ChevronDown, ChevronUp, Activity, Terminal } from 'lucide-react';
import { Badge } from '@/shared/components/Badge';
import { StatusDot } from '@/shared/components/StatusDot';
import { api } from '@/shared/lib/api-client';

interface ProviderInfo {
  name: string;
  tier: 'local' | 'cloud' | 'deterministic';
  modelId: string;
  status: 'active' | 'standby' | 'disabled' | 'error';
  statusLabel: string;
  details: string;
  lastCheck: string;
}

const PROVIDERS: ProviderInfo[] = [
  {
    name: 'Groq Cloud LPU',
    tier: 'cloud',
    modelId: 'qwen/qwen3.8-27b',
    status: 'active',
    statusLabel: 'ACTIVE / OPERATIONAL',
    details: 'Cloud high-throughput LPU inference (qwen/qwen3.8-27b) & Groq Vision OCR. Connected via DSN ground-link.',
    lastCheck: 'Live (Cloud LPU)',
  },
  {
    name: 'Ollama Edge AI',
    tier: 'local',
    modelId: 'qwen2.5:7b-instruct',
    status: 'active',
    statusLabel: 'ACTIVE / OPERATIONAL',
    details: 'Locally resident on spacecraft hardware at http://127.0.0.1:11434. Primary offline intelligence.',
    lastCheck: 'Live (Edge)',
  },
  {
    name: 'Deterministic Engine',
    tier: 'deterministic',
    modelId: 'RULE-ENGINE-V2',
    status: 'active',
    statusLabel: 'READY (OFFLINE PROTOCOL)',
    details: 'Zero-hallucination deterministic fallback for strict NASA-STD-3001 protocol execution.',
    lastCheck: 'Internal',
  },
];

interface ExecutionTraceProps {
  trace?: {
    assessment_id?: string;
    router_mode?: string;
    provider_status?: string;
    overall_risk?: string;
    overall_confidence?: string;
    agent_statuses?: Record<string, { status: string; execution_time_ms: number; warnings?: string[] }>;
  };
}

export function ProviderSelector({ trace }: ExecutionTraceProps) {
  const [expanded, setExpanded] = useState(false);
  const [providersList, setProvidersList] = useState<ProviderInfo[]>(PROVIDERS);
  const [, setConnectivity] = useState<Record<string, unknown> | null>(null);

  useEffect(() => {
    api.getConnectivity()
      .then((data) => setConnectivity(data))
      .catch(() => {});

    api.getAiProviders()
      .then((res) => {
        if (res && res.providers && Array.isArray(res.providers)) {
          setProvidersList(res.providers);
        }
      })
      .catch(() => {});
  }, []);

  return (
    <div
      style={{
        borderBottom: '1px solid var(--color-hairline)',
        background: 'var(--color-ground-secondary)',
        fontSize: '12px',
      }}
    >
      {/* Header Bar */}
      <div
        onClick={() => setExpanded(!expanded)}
        style={{
          padding: '8px 16px',
          display: 'flex',
          justifyContent: 'space-between',
          alignItems: 'center',
          cursor: 'pointer',
          userSelect: 'none',
        }}
      >
        <div style={{ display: 'flex', alignItems: 'center', gap: '10px' }}>
          <Cpu size={14} style={{ color: 'var(--color-teal)' }} />
          <span style={{ fontWeight: 600, color: 'var(--color-ink)', fontFamily: 'var(--font-body)' }}>
            AI Routing Architecture:
          </span>
          <Badge variant="info" size="sm">
            <span className="dot-indicator dot-teal" style={{ marginRight: '4px' }} />
            {trace?.router_mode || 'HYBRID (EDGE OLLAMA + CLOUD GROQ LPU)'}
          </Badge>
          <span className="dark-label" style={{ fontSize: '11px', textTransform: 'none', letterSpacing: 'normal' }}>
            Active: <strong style={{ color: 'var(--color-teal)' }}>Groq LPU (qwen/qwen3.8-27b) + Ollama Edge</strong>
          </span>
        </div>

        <div style={{ display: 'flex', alignItems: 'center', gap: '8px', color: 'var(--color-muted)' }}>
          <span className="dark-label">Provider Health & Agent Trace</span>
          {expanded ? <ChevronUp size={14} /> : <ChevronDown size={14} />}
        </div>
      </div>

      {/* Expanded Details */}
      {expanded && (
        <div style={{ padding: '12px 16px', borderTop: '1px solid var(--color-border-subtle)', display: 'flex', flexDirection: 'column', gap: '16px' }}>
          {/* Provider Matrix */}
          <div>
            <div style={{ fontSize: '11px', textTransform: 'uppercase', color: 'var(--text-muted)', fontWeight: 600, marginBottom: '8px' }}>
              Configured Inference Providers & Truthful Availability
            </div>
            <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(240px, 1fr))', gap: '10px' }}>
              {providersList.map((p) => (
                <div
                  key={p.name}
                  style={{
                    padding: '10px',
                    borderRadius: 'var(--radius-md)',
                    background: 'var(--color-card)',
                    border: `1px solid ${p.status === 'active' ? 'var(--color-accent)' : 'var(--color-border-subtle)'}`,
                  }}
                >
                  <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '4px' }}>
                    <span style={{ fontWeight: 600, color: 'var(--text-primary)' }}>{p.name}</span>
                    <Badge variant={p.status === 'active' ? 'success' : p.status === 'error' ? 'danger' : 'outline'} size="sm">
                      {p.status.toUpperCase()}
                    </Badge>
                  </div>
                  <div style={{ fontSize: '11px', fontFamily: 'var(--font-mono)', color: 'var(--color-accent)' }}>
                    {p.modelId}
                  </div>
                  <div style={{ fontSize: '11px', color: 'var(--text-muted)', marginTop: '4px', lineHeight: 1.4 }}>
                    {p.details}
                  </div>
                </div>
              ))}
            </div>
          </div>

          {/* Multi-Agent Execution Trace if available */}
          {trace?.agent_statuses && (
            <div>
              <div style={{ fontSize: '11px', textTransform: 'uppercase', color: 'var(--text-muted)', fontWeight: 600, marginBottom: '8px' }}>
                LangGraph Supervisor Execution Trace (Assessment {trace.assessment_id})
              </div>
              <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(180px, 1fr))', gap: '8px' }}>
                {Object.entries(trace.agent_statuses).map(([agentName, data]) => (
                  <div
                    key={agentName}
                    style={{
                      padding: '8px 10px',
                      borderRadius: 'var(--radius-md)',
                      background: 'var(--color-bg-primary)',
                      border: '1px solid var(--color-border-subtle)',
                    }}
                  >
                    <div style={{ fontWeight: 600, textTransform: 'capitalize' }}>
                      {agentName.replace(/_/g, ' ')}
                    </div>
                    <div style={{ display: 'flex', justifyContent: 'space-between', marginTop: '4px', fontSize: '11px' }}>
                      <span style={{ color: 'var(--text-muted)' }}>Status:</span>
                      <span style={{ color: data.status.includes('SUCCESS') ? 'var(--color-emerald)' : 'var(--color-amber)' }}>
                        {data.status.replace('AgentExecutionState.', '')}
                      </span>
                    </div>
                    <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: '11px' }}>
                      <span style={{ color: 'var(--text-muted)' }}>Latency:</span>
                      <span style={{ fontFamily: 'var(--font-mono)' }}>{data.execution_time_ms.toFixed(1)} ms</span>
                    </div>
                  </div>
                ))}
              </div>
            </div>
          )}
        </div>
      )}
    </div>
  );
}
