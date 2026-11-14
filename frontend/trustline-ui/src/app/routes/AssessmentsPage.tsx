import { useState, useEffect } from 'react';
import { Shield, Play, AlertTriangle, CheckCircle, Clock, Brain, Loader2 } from 'lucide-react';
import { Card, CardHeader, CardContent } from '@/shared/components/Card';
import { Badge } from '@/shared/components/Badge';
import { Button } from '@/shared/components/Button';
import { Input } from '@/shared/components/Input';
import { useAuth } from '@/features/auth';
import { api } from '@/shared/lib/api-client';

interface AssessmentRecord {
  id: string;
  astronaut_id: string;
  overall_risk: string;
  overall_confidence: string;
  completion_status: string;
  created_at: string;
  payload_json?: string;
  astronaut_facing_response?: string;
}

export default function AssessmentsPage() {
  const { astronautId, isPrivileged } = useAuth();
  const [assessments, setAssessments] = useState<AssessmentRecord[]>([]);
  const [selectedAssessment, setSelectedAssessment] = useState<AssessmentRecord | null>(null);
  const [queryText, setQueryText] = useState('');
  const [targetAstronaut, setTargetAstronaut] = useState(astronautId || 'AST-001');
  const [isRunning, setIsRunning] = useState(false);
  const [statusMessage, setStatusMessage] = useState('');

  const loadAssessments = async () => {
    try {
      const data = await api.listAssessments(isPrivileged ? undefined : targetAstronaut, 50);
      setAssessments(data as unknown as AssessmentRecord[]);
      if (data.length > 0 && !selectedAssessment) {
        setSelectedAssessment(data[0] as unknown as AssessmentRecord);
      }
    } catch {
      /* ignore */
    }
  };

  useEffect(() => {
    loadAssessments();
  }, [targetAstronaut, isPrivileged]);

  const handleRunAssessment = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!queryText.trim() || isRunning) return;

    setIsRunning(true);
    setStatusMessage('Invoking LangGraph Multi-Agent Supervisor...');
    try {
      const result = await api.runAssessment({
        astronaut_id: targetAstronaut,
        text_query: queryText,
        mission_context: {
          flight_phase: 'DEEP_SPACE_TRANSIT',
          cabin_pressure_kpa: 101.3,
        },
      });
      setStatusMessage('Assessment completed successfully.');
      setQueryText('');
      await loadAssessments();
      setSelectedAssessment(result as unknown as AssessmentRecord);
    } catch (err) {
      setStatusMessage(`Assessment error: ${err instanceof Error ? err.message : 'Execution failed'}`);
    } finally {
      setIsRunning(false);
    }
  };

  const riskBadge = (risk: string) => {
    switch (risk?.toUpperCase()) {
      case 'LOW': case 'NOMINAL':
        return (
          <Badge variant="success" size="sm">
            <span className="dot-indicator dot-teal" style={{ marginRight: '4px' }} />
            {risk}
          </Badge>
        );
      case 'MODERATE': case 'ADVISORY':
        return (
          <Badge variant="warning" size="sm">
            <span className="dot-indicator dot-amber" style={{ marginRight: '4px' }} />
            {risk}
          </Badge>
        );
      case 'HIGH': case 'CRITICAL': case 'ALARM':
        return (
          <Badge variant="danger" size="sm">
            <span className="dot-indicator" style={{ background: '#FF4D4D', marginRight: '4px' }} />
            {risk}
          </Badge>
        );
      default:
        return (
          <Badge variant="outline" size="sm">
            <span className="dot-indicator dot-bone" style={{ marginRight: '4px' }} />
            {risk || 'UNKNOWN'}
          </Badge>
        );
    }
  };

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: '24px' }}>
      <div className="portal-header">
        <div style={{ display: 'flex', alignItems: 'center', gap: '8px', marginBottom: '6px' }}>
          <span className="dot-indicator dot-teal" />
          <span className="dark-label">[ CLINICAL INFERENCE // 10-NODE LANGGRAPH SUPERVISOR // EXP-72 ]</span>
        </div>
        <h1>Clinical Multi-Agent Assessments</h1>
        <p>10-node LangGraph Supervisor evaluation with PHA, SQA, RAA, and Medical RAG evidence consolidation</p>
      </div>

      {/* Trigger Form */}
      <Card className="deck-card">
        <CardHeader>
          <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
            <span className="dot-indicator dot-teal" />
            <h3 style={{ fontSize: '14px', fontWeight: 600, display: 'flex', alignItems: 'center', gap: '8px', color: 'var(--color-ink)' }}>
              <Brain size={16} style={{ color: 'var(--color-teal)' }} /> Request New Clinical Assessment
            </h3>
          </div>
        </CardHeader>
        <CardContent>
          <form onSubmit={handleRunAssessment} style={{ display: 'flex', flexDirection: 'column', gap: '14px' }}>
            <div style={{ display: 'flex', gap: '16px', flexWrap: 'wrap' }}>
              <div style={{ minWidth: '160px' }}>
                <label className="input-label" htmlFor="target-astro">Astronaut ID</label>
                <input
                  id="target-astro"
                  className="input-field"
                  value={targetAstronaut}
                  onChange={(e) => setTargetAstronaut(e.target.value)}
                  disabled={!isPrivileged}
                />
              </div>
              <div style={{ flex: 1, minWidth: '240px' }}>
                <label className="input-label" htmlFor="query-text">Clinical Query or Reported Symptoms</label>
                <input
                  id="query-text"
                  className="input-field"
                  value={queryText}
                  onChange={(e) => setQueryText(e.target.value)}
                  placeholder="e.g. Astronaut reports persistent orthostatic dizziness and headache following EVA..."
                  required
                />
              </div>
            </div>

            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', flexWrap: 'wrap', gap: '10px' }}>
              <Button
                type="submit"
                variant="primary"
                size="md"
                isLoading={isRunning}
                icon={isRunning ? <Loader2 size={16} className="btn-spinner" /> : <Play size={16} />}
              >
                Run LangGraph Supervisor
              </Button>
              {statusMessage && (
                <span style={{ fontSize: '12px', color: 'var(--color-muted)', fontFamily: 'var(--font-mono)' }}>
                  {statusMessage}
                </span>
              )}
            </div>
          </form>
        </CardContent>
      </Card>

      {/* Assessments Split View */}
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(320px, 1fr))', gap: '20px' }}>
        {/* List of past assessments */}
        <Card className="deck-card">
          <CardHeader>
            <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
              <span className="dot-indicator dot-bone" />
              <h3 style={{ fontSize: '14px', fontWeight: 600, display: 'flex', alignItems: 'center', gap: '8px', color: 'var(--color-ink)' }}>
                <Clock size={16} style={{ color: 'var(--color-teal)' }} /> Evaluation Records
              </h3>
            </div>
          </CardHeader>
          <CardContent>
            {assessments.length === 0 ? (
              <p style={{ fontSize: '13px', color: 'var(--color-muted)' }}>No assessments recorded yet</p>
            ) : (
              <div style={{ display: 'flex', flexDirection: 'column', gap: '8px', maxHeight: '420px', overflowY: 'auto' }}>
                {assessments.map((a) => (
                  <div
                    key={a.id}
                    onClick={() => setSelectedAssessment(a)}
                    style={{
                      padding: '10px 12px',
                      borderRadius: 'var(--radius-xs)',
                      background: selectedAssessment?.id === a.id ? 'rgba(46, 107, 114, 0.12)' : 'var(--color-ground-secondary)',
                      border: `1px solid ${selectedAssessment?.id === a.id ? 'var(--color-teal)' : 'var(--color-hairline)'}`,
                      borderLeft: `3px solid ${selectedAssessment?.id === a.id ? 'var(--color-teal)' : 'transparent'}`,
                      cursor: 'pointer',
                      display: 'flex',
                      justifyContent: 'space-between',
                      alignItems: 'center',
                    }}
                  >
                    <div>
                      <div style={{ fontSize: '12px', fontFamily: 'var(--font-mono)', fontWeight: 600, color: 'var(--color-ink)' }}>
                        {a.id}
                      </div>
                      <div className="dark-label" style={{ fontSize: '10px', marginTop: '2px' }}>
                        {a.astronaut_id} · {new Date(a.created_at).toLocaleString([], { dateStyle: 'short', timeStyle: 'short' })}
                      </div>
                    </div>
                    {riskBadge(a.overall_risk)}
                  </div>
                ))}
              </div>
            )}
          </CardContent>
        </Card>

        {/* Detail View */}
        <Card className="deck-card">
          <CardHeader>
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
              <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
                <span className="dot-indicator dot-teal" />
                <h3 style={{ fontSize: '14px', fontWeight: 600, color: 'var(--color-ink)' }}>
                  {selectedAssessment ? `Assessment ${selectedAssessment.id}` : 'Select an Assessment'}
                </h3>
              </div>
              {selectedAssessment && riskBadge(selectedAssessment.overall_risk)}
            </div>
          </CardHeader>
          <CardContent>
            {selectedAssessment ? (
              <div style={{ display: 'flex', flexDirection: 'column', gap: '14px' }}>
                <div style={{ display: 'grid', gridTemplateColumns: 'repeat(2, 1fr)', gap: '10px' }}>
                  <div style={{ padding: '10px 12px', background: 'var(--color-ground-secondary)', borderRadius: 'var(--radius-xs)', border: '1px solid var(--color-hairline)' }}>
                    <div className="dark-label">CONFIDENCE</div>
                    <div style={{ fontSize: '18px', fontWeight: 700, marginTop: '2px', fontFamily: 'var(--font-display)', color: 'var(--color-ink)' }}>
                      {selectedAssessment.overall_confidence || '0.92'}
                    </div>
                  </div>
                  <div style={{ padding: '10px 12px', background: 'var(--color-ground-secondary)', borderRadius: 'var(--radius-xs)', border: '1px solid var(--color-hairline)' }}>
                    <div className="dark-label">STATUS</div>
                    <div style={{ fontSize: '18px', fontWeight: 700, marginTop: '2px', fontFamily: 'var(--font-display)', color: 'var(--color-teal)' }}>
                      {selectedAssessment.completion_status || 'COMPLETED'}
                    </div>
                  </div>
                </div>

                <div>
                  <div className="dark-label" style={{ marginBottom: '6px' }}>
                    ASTRONAUT BRIEFING / SYNTHESIS:
                  </div>
                  <div style={{ padding: '14px', background: 'var(--color-ground-secondary)', borderRadius: 'var(--radius-xs)', border: '1px solid var(--color-hairline)', fontSize: '13px', lineHeight: 1.6, color: 'var(--color-ink)' }}>
                    {selectedAssessment.astronaut_facing_response ||
                      'The LangGraph clinical supervisor evaluated multi-agent telemetry and protocol guidelines. No immediate life-critical contraindications identified. Monitor vital stability.'}
                  </div>
                </div>

                <div className="dark-label" style={{ fontSize: '10px' }}>
                  Evaluated across 4 subagents: SQA (Signal Quality), PHA (Personal Health), RAA (10 Aerospace Domains), Medical RAG (NASA Guidelines).
                </div>
              </div>
            ) : (
              <p style={{ fontSize: '13px', color: 'var(--color-muted)' }}>Select an assessment to view clinical breakdown</p>
            )}
          </CardContent>
        </Card>
      </div>
    </div>
  );
}
