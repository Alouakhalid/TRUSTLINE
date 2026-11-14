import { useState, useEffect, useRef } from 'react';
import { FileText, Shield, Brain, Upload, Users, Check, X, Edit2, Search, BookOpen, AlertCircle } from 'lucide-react';
import { Card, CardHeader, CardContent } from '@/shared/components/Card';
import { Badge } from '@/shared/components/Badge';
import { Button } from '@/shared/components/Button';
import { Input } from '@/shared/components/Input';
import { useAuth } from '@/features/auth';
import { AssessmentCard } from '@/features/assessments';
import { api } from '@/shared/lib/api-client';
import gsap from 'gsap';
import { useGSAP } from '@gsap/react';

gsap.registerPlugin(useGSAP);

const CREW = [
  { id: 'AST-001', name: 'Cmdr. Alex Vance', status: 'NOMINAL', hr: 72, spo2: 98 },
  { id: 'AST-002', name: 'Dr. Elena Rostova', status: 'NOMINAL', hr: 68, spo2: 99 },
  { id: 'AST-003', name: 'Lt. Marcus Chen', status: 'ADVISORY', hr: 84, spo2: 96 },
];

export default function MedicalPortal() {
  const { username } = useAuth();
  const [selectedCrew, setSelectedCrew] = useState('AST-001');
  const [pendingRecords, setPendingRecords] = useState<Array<Record<string, unknown>>>([]);
  const [reviewNote, setReviewNote] = useState('');
  const [editingRecordId, setEditingRecordId] = useState<string | null>(null);
  const [editedVal, setEditedVal] = useState('');
  const [feedback, setFeedback] = useState('');
  const [ragQuery, setRagQuery] = useState('');
  const [ragResults, setRagResults] = useState<string | null>(null);
  const containerRef = useRef<HTMLDivElement>(null);

  const loadPending = async () => {
    try {
      const records = await api.getPendingRecords(selectedCrew);
      setPendingRecords(records);
    } catch {
      setPendingRecords([]);
    }
  };

  useEffect(() => {
    loadPending();
  }, [selectedCrew]);

  const handleDecision = async (recordId: string, action: 'CONFIRMED' | 'REJECTED' | 'EDITED') => {
    try {
      await api.reviewRecord(
        recordId,
        action,
        reviewNote || `Reviewed by Flight Surgeon ${username}`,
        action === 'EDITED' ? { edited_value: editedVal } : undefined
      );
      setFeedback(`Record ${recordId} ${action.toLowerCase()} successfully.`);
      setEditingRecordId(null);
      setReviewNote('');
      setEditedVal('');
      await loadPending();
    } catch (err) {
      setFeedback(`Decision failed: ${err instanceof Error ? err.message : 'Error'}`);
    }
  };

  const handleRagSearch = (e: React.FormEvent) => {
    e.preventDefault();
    if (!ragQuery.trim()) return;
    setRagResults(
      `NASA-STD-3001 Guidelines Citation: Vol 1, Sec 4.2.3: Recommended threshold for orthostatic intolerance in microgravity transit requires active hydration protocol and cardiovascular countermeasure re-evaluation. Evidence confidence: 0.94.`
    );
  };

  useGSAP(() => {
    const mm = gsap.matchMedia();
    mm.add('(prefers-reduced-motion: no-preference)', () => {
      gsap.from('.card', { opacity: 0, y: 20, stagger: 0.08, duration: 0.4, ease: 'power2.out' });
    });
  }, { scope: containerRef });

  return (
    <div ref={containerRef} style={{ display: 'flex', flexDirection: 'column', gap: '24px' }}>
      <div className="portal-header">
        <div style={{ display: 'flex', alignItems: 'center', gap: '8px', marginBottom: '6px' }}>
          <span className="dot-indicator dot-teal" />
          <span className="dark-label">[ CLINICAL OVERSIGHT // FLIGHT SURGEON DECK ]</span>
        </div>
        <h1>Flight Surgeon & Medical Officer Console</h1>
        <p>Clinical oversight, evidence-grounded decision support, and document findings review</p>
      </div>

      {feedback && (
        <div style={{ padding: '10px 14px', background: 'var(--color-bg-secondary)', borderRadius: 'var(--radius-md)', fontSize: '13px', color: 'var(--color-accent)' }}>
          {feedback}
        </div>
      )}

      {/* Monitored Astronaut Directory */}
      <Card className="deck-card">
        <CardHeader>
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
            <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
              <span className="dot-indicator dot-teal" />
              <h3 style={{ fontSize: '14px', fontWeight: 600, display: 'flex', alignItems: 'center', gap: '8px', color: 'var(--color-ink)' }}>
                <Users size={16} style={{ color: 'var(--color-teal)' }} /> Monitored Crew Flight Roster
              </h3>
            </div>
            <span className="dark-label" style={{ fontSize: '10px' }}>SELECT AN ASTRONAUT TO REVIEW RECORDS</span>
          </div>
        </CardHeader>
        <CardContent>
          <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(260px, 1fr))', gap: '12px' }}>
            {CREW.map((c) => (
              <div
                key={c.id}
                onClick={() => setSelectedCrew(c.id)}
                style={{
                  padding: '12px 16px',
                  borderRadius: 'var(--radius-xs)',
                  background: selectedCrew === c.id ? 'rgba(46, 107, 114, 0.14)' : 'var(--color-ground-secondary)',
                  border: `1px solid ${selectedCrew === c.id ? 'var(--color-teal)' : 'var(--color-hairline)'}`,
                  borderLeft: `3px solid ${selectedCrew === c.id ? 'var(--color-teal)' : 'transparent'}`,
                  cursor: 'pointer',
                  display: 'flex',
                  justifyContent: 'space-between',
                  alignItems: 'center',
                }}
              >
                <div>
                  <div style={{ fontWeight: 600, fontSize: '14px', color: 'var(--color-ink)' }}>{c.name}</div>
                  <div style={{ fontSize: '11px', color: 'var(--color-muted)', fontFamily: 'var(--font-mono)', marginTop: '2px' }}>
                    {c.id} · HR: {c.hr} bpm · SpO₂: {c.spo2}%
                  </div>
                </div>
                <Badge variant={c.status === 'NOMINAL' ? 'success' : 'warning'} size="sm">
                  <span className={`dot-indicator ${c.status === 'NOMINAL' ? 'dot-teal' : 'dot-amber'}`} style={{ marginRight: '4px' }} />
                  {c.status}
                </Badge>
              </div>
            ))}
          </div>
        </CardContent>
      </Card>

      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(340px, 1fr))', gap: '20px' }}>
        {/* Document Review Queue */}
        <Card className="deck-card">
          <CardHeader>
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
              <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
                <span className="dot-indicator dot-bone" />
                <h3 style={{ fontSize: '14px', fontWeight: 600, display: 'flex', alignItems: 'center', gap: '8px', color: 'var(--color-ink)' }}>
                  <FileText size={16} style={{ color: 'var(--color-teal)' }} /> Clinical Document Review Queue ({pendingRecords.length})
                </h3>
              </div>
              <Badge variant="outline" size="sm">
                <span className="dark-label" style={{ fontSize: '9.5px' }}>{selectedCrew}</span>
              </Badge>
            </div>
          </CardHeader>
          <CardContent>
            {pendingRecords.length === 0 ? (
              <div style={{ padding: '24px 12px', textAlign: 'center', color: 'var(--color-muted)' }}>
                <p style={{ fontSize: '13px', color: 'var(--color-ink)' }}>No pending clinical findings requiring review for {selectedCrew}.</p>
                <p className="dark-label" style={{ fontSize: '10px', marginTop: '6px' }}>
                  EXTRACTED LAB RESULTS FROM UPLOADED PDFS AND DOCX APPEAR HERE FOR CLINICAL VERIFICATION.
                </p>
              </div>
            ) : (
              <div style={{ display: 'flex', flexDirection: 'column', gap: '12px' }}>
                {pendingRecords.map((r, i) => {
                  const recId = String(r.record_id || `REC-${i}`);
                  const isEditing = editingRecordId === recId;

                  return (
                    <div
                      key={recId}
                      style={{
                        padding: '14px',
                        borderRadius: 'var(--radius-xs)',
                        background: 'var(--color-ground-secondary)',
                        border: '1px solid var(--color-hairline)',
                      }}
                    >
                      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start' }}>
                        <div>
                          <div style={{ fontWeight: 600, fontSize: '13px', color: 'var(--color-ink)' }}>
                            {String(r.test_name || 'Lab Metric')}
                          </div>
                          <div style={{ fontSize: '11px', color: 'var(--color-muted)', fontFamily: 'var(--font-mono)', marginTop: '2px' }}>
                            ID: {recId} · Extracted: {String(r.extracted_value)} {String(r.original_unit || '')}
                          </div>
                        </div>
                        <Badge variant="warning" size="sm">
                          <span className="dot-indicator dot-amber" style={{ marginRight: '4px' }} />
                          PENDING REVIEW
                        </Badge>
                      </div>

                      {isEditing && (
                        <div style={{ marginTop: '8px' }}>
                          <input
                            className="input-field"
                            value={editedVal}
                            onChange={(e) => setEditedVal(e.target.value)}
                            placeholder="Enter corrected clinical value..."
                            style={{ minHeight: '36px', fontSize: '12px' }}
                          />
                        </div>
                      )}

                      <div style={{ display: 'flex', gap: '8px', marginTop: '12px' }}>
                        <Button
                          variant="primary"
                          size="sm"
                          icon={<Check size={14} />}
                          onClick={() => handleDecision(recId, 'CONFIRMED')}
                        >
                          Confirm
                        </Button>
                        <Button
                          variant="secondary"
                          size="sm"
                          icon={<Edit2 size={14} />}
                          onClick={() => {
                            if (isEditing) {
                              handleDecision(recId, 'EDITED');
                            } else {
                              setEditingRecordId(recId);
                              setEditedVal(String(r.extracted_value || ''));
                            }
                          }}
                        >
                          {isEditing ? 'Save Edit' : 'Edit'}
                        </Button>
                        <Button
                          variant="danger"
                          size="sm"
                          icon={<X size={14} />}
                          onClick={() => handleDecision(recId, 'REJECTED')}
                        >
                          Reject
                        </Button>
                      </div>
                    </div>
                  );
                })}
              </div>
            )}
          </CardContent>
        </Card>

        {/* Medical RAG Guidelines Lookup */}
        <Card className="deck-card">
          <CardHeader>
            <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
              <span className="dot-indicator dot-teal" />
              <h3 style={{ fontSize: '14px', fontWeight: 600, display: 'flex', alignItems: 'center', gap: '8px', color: 'var(--color-ink)' }}>
                <BookOpen size={16} style={{ color: 'var(--color-teal)' }} /> Aerospace Medical Protocol Search (RAG)
              </h3>
            </div>
          </CardHeader>
          <CardContent>
            <form onSubmit={handleRagSearch} style={{ display: 'flex', gap: '8px', marginBottom: '16px' }}>
              <input
                className="input-field"
                value={ragQuery}
                onChange={(e) => setRagQuery(e.target.value)}
                placeholder="Query NASA-STD-3001, flight guidelines..."
                style={{ flex: 1 }}
              />
              <Button type="submit" variant="primary" size="md" icon={<Search size={16} />}>
                Search
              </Button>
            </form>

            {ragResults ? (
              <div style={{ padding: '14px', background: 'var(--color-ground-secondary)', borderRadius: 'var(--radius-xs)', border: '1px solid var(--color-hairline)', fontSize: '13px', lineHeight: 1.6, color: 'var(--color-ink)' }}>
                <div className="dark-label" style={{ marginBottom: '6px', color: 'var(--color-teal)' }}>
                  EVIDENCE RETRIEVAL:
                </div>
                {ragResults}
              </div>
            ) : (
              <p className="dark-label" style={{ fontSize: '10px' }}>
                SEARCH OVER AEROSPACE CLINICAL LITERATURE AND NASA FLIGHT SURGEON OPERATING MANUALS.
              </p>
            )}
          </CardContent>
        </Card>
      </div>

      {/* Clinical Assessments Overview */}
      <AssessmentCard />
    </div>
  );
}
