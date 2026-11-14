import { useState, useEffect } from 'react';
import { Shield, Clock, AlertTriangle, CheckCircle } from 'lucide-react';
import { Card, CardHeader, CardContent } from '@/shared/components/Card';
import { Badge } from '@/shared/components/Badge';
import { Skeleton } from '@/shared/components/Skeleton';
import { listAssessments } from '../api/assessments';
import { useAuthStore } from '@/features/auth/stores/auth-store';

interface Assessment {
  id: string;
  astronaut_id: string;
  overall_risk: string;
  overall_confidence: string;
  completion_status: string;
  created_at: string;
}

export function AssessmentCard({ className = '' }: { className?: string }) {
  const { astronautId } = useAuthStore();
  const [assessments, setAssessments] = useState<Assessment[]>([]);
  const [isLoading, setIsLoading] = useState(true);

  useEffect(() => {
    async function load() {
      try {
        const data = await listAssessments(astronautId || undefined, 5);
        setAssessments(data as unknown as Assessment[]);
      } catch {
        /* ignore */
      } finally {
        setIsLoading(false);
      }
    }
    load();
  }, [astronautId]);

  const riskVariant = (risk: string) => {
    switch (risk?.toUpperCase()) {
      case 'LOW': return 'success';
      case 'MODERATE': return 'warning';
      case 'HIGH': case 'CRITICAL': return 'danger';
      default: return 'outline';
    }
  };

  const RiskIcon = ({ risk }: { risk: string }) => {
    switch (risk?.toUpperCase()) {
      case 'LOW': return <CheckCircle size={14} aria-hidden="true" />;
      case 'HIGH': case 'CRITICAL': return <AlertTriangle size={14} aria-hidden="true" />;
      default: return <Shield size={14} aria-hidden="true" />;
    }
  };

  if (isLoading) {
    return (
      <Card className={className}>
        <CardHeader><Skeleton width="60%" height={20} /></CardHeader>
        <CardContent><Skeleton height={60} /><Skeleton height={60} /></CardContent>
      </Card>
    );
  }

  return (
    <Card className={className}>
      <CardHeader>
        <h3 style={{ fontSize: '14px', fontWeight: 600, display: 'flex', alignItems: 'center', gap: '8px' }}>
          <Shield size={16} aria-hidden="true" />
          Recent Assessments
        </h3>
      </CardHeader>
      <CardContent>
        {assessments.length === 0 ? (
          <p style={{ color: 'var(--text-muted)', fontSize: '13px' }}>No assessments yet</p>
        ) : (
          <div style={{ display: 'flex', flexDirection: 'column', gap: '8px' }}>
            {assessments.map((a) => (
              <div
                key={a.id}
                style={{
                  display: 'flex',
                  alignItems: 'center',
                  justifyContent: 'space-between',
                  padding: '8px 12px',
                  borderRadius: 'var(--radius-md)',
                  background: 'var(--color-bg-secondary)',
                  border: '1px solid var(--color-border-subtle)',
                }}
              >
                <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
                  <RiskIcon risk={a.overall_risk} />
                  <span style={{ fontSize: '12px', fontFamily: 'var(--font-mono)' }}>
                    {a.id.slice(0, 12)}
                  </span>
                </div>
                <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
                  <Badge variant={riskVariant(a.overall_risk)} size="sm">
                    {a.overall_risk || 'UNKNOWN'}
                  </Badge>
                  <span style={{ fontSize: '11px', color: 'var(--text-muted)', display: 'flex', alignItems: 'center', gap: '4px' }}>
                    <Clock size={11} aria-hidden="true" />
                    {new Date(a.created_at).toLocaleDateString()}
                  </span>
                </div>
              </div>
            ))}
          </div>
        )}
      </CardContent>
    </Card>
  );
}
