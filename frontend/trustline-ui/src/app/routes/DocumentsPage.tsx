import { useState, useRef } from 'react';
import { Upload, FileText, CheckCircle, AlertCircle, Loader2 } from 'lucide-react';
import { Card, CardHeader, CardContent } from '@/shared/components/Card';
import { Badge } from '@/shared/components/Badge';
import { Button } from '@/shared/components/Button';
import { useAuth } from '@/features/auth';
import { api } from '@/shared/lib/api-client';

interface UploadedDoc {
  id: string;
  filename: string;
  status: string;
  created_at: string;
}

export default function DocumentsPage() {
  const { astronautId } = useAuth();
  const [docs, setDocs] = useState<UploadedDoc[]>([]);
  const [isUploading, setIsUploading] = useState(false);
  const [uploadStatus, setUploadStatus] = useState<string>('');
  const fileInputRef = useRef<HTMLInputElement>(null);

  const handleFileChange = async (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (!file) return;

    setIsUploading(true);
    setUploadStatus(`Uploading ${file.name}...`);
    try {
      const res = await api.uploadDocument(file, astronautId);
      const newDoc: UploadedDoc = {
        id: (res.document_id as string) || `DOC-${Date.now().toString(16).toUpperCase()}`,
        filename: file.name,
        status: (res.status as string) || 'UPLOADED',
        created_at: new Date().toISOString(),
      };
      setDocs((prev) => [newDoc, ...prev]);
      setUploadStatus(`Successfully uploaded ${file.name}. OCR text extraction pipeline queued.`);
    } catch (err) {
      setUploadStatus(`Upload failed: ${err instanceof Error ? err.message : 'Error'}`);
    } finally {
      setIsUploading(false);
      if (fileInputRef.current) fileInputRef.current.value = '';
    }
  };

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: '24px' }}>
      <div className="portal-header">
        <div style={{ display: 'flex', alignItems: 'center', gap: '8px', marginBottom: '6px' }}>
          <span className="dot-indicator dot-teal" />
          <span className="dark-label">[ INGESTION // CLINICAL DOCUMENT INTELLIGENCE // EXP-72 ]</span>
        </div>
        <h1>Medical Document Intelligence Gateway</h1>
        <p>In-flight ingestion with PyMuPDF native extraction, python-docx, and Groq Vision OCR</p>
      </div>

      {/* Upload Zone */}
      <Card className="deck-card">
        <CardHeader>
          <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
            <span className="dot-indicator dot-teal" />
            <h3 style={{ fontSize: '14px', fontWeight: 600, display: 'flex', alignItems: 'center', gap: '8px', color: 'var(--color-ink)' }}>
              <Upload size={16} style={{ color: 'var(--color-teal)' }} /> Clinical Document Ingestion
            </h3>
          </div>
        </CardHeader>
        <CardContent>
          <div
            onClick={() => fileInputRef.current?.click()}
            style={{
              border: '1px dashed var(--color-hairline)',
              borderRadius: 'var(--radius-xs)',
              padding: '40px 20px',
              textAlign: 'center',
              cursor: 'pointer',
              background: 'var(--color-ground-secondary)',
              transition: 'border-color var(--duration-fast) var(--ease-out)',
            }}
          >
            <input
              type="file"
              ref={fileInputRef}
              onChange={handleFileChange}
              accept=".pdf,.docx,.txt"
              style={{ display: 'none' }}
            />
            {isUploading ? (
              <Loader2 size={36} className="btn-spinner" style={{ margin: '0 auto 12px', color: 'var(--color-teal)' }} />
            ) : (
              <FileText size={36} style={{ margin: '0 auto 12px', color: 'var(--color-teal)' }} />
            )}
            <p style={{ fontSize: '15px', fontWeight: 600, color: 'var(--color-ink)' }}>Click or drop files here to upload</p>
            <p className="dark-label" style={{ marginTop: '6px' }}>
              SUPPORTED: PDF, DOCX, TXT (UP TO 10MB) · PATIENT TAG: {astronautId || 'AST-001'}
            </p>
          </div>

          {uploadStatus && (
            <p style={{ fontSize: '12px', marginTop: '12px', color: 'var(--color-teal)', fontFamily: 'var(--font-mono)' }}>
              {uploadStatus}
            </p>
          )}
        </CardContent>
      </Card>

      {/* Ingested Documents List */}
      <Card className="deck-card">
        <CardHeader>
          <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
            <span className="dot-indicator dot-bone" />
            <h3 style={{ fontSize: '14px', fontWeight: 600, display: 'flex', alignItems: 'center', gap: '8px', color: 'var(--color-ink)' }}>
              <FileText size={16} style={{ color: 'var(--color-teal)' }} /> Ingested Clinical Records
            </h3>
          </div>
        </CardHeader>
        <CardContent>
          {docs.length === 0 ? (
            <p style={{ fontSize: '13px', color: 'var(--color-muted)' }}>
              No documents uploaded yet in this mission session. Upload clinical lab notes, ECG scans, or PDF flight health logs.
            </p>
          ) : (
            <div style={{ display: 'flex', flexDirection: 'column', gap: '8px' }}>
              {docs.map((d) => (
                <div
                  key={d.id}
                  style={{
                    display: 'flex',
                    alignItems: 'center',
                    justifyContent: 'space-between',
                    padding: '10px 14px',
                    borderRadius: 'var(--radius-xs)',
                    background: 'var(--color-ground-secondary)',
                    border: '1px solid var(--color-hairline)',
                  }}
                >
                  <div style={{ display: 'flex', alignItems: 'center', gap: '10px' }}>
                    <FileText size={18} style={{ color: 'var(--color-teal)' }} />
                    <div>
                      <div style={{ fontSize: '13px', fontWeight: 500, color: 'var(--color-ink)' }}>{d.filename}</div>
                      <div style={{ fontSize: '11px', color: 'var(--color-muted)', fontFamily: 'var(--font-mono)' }}>
                        {d.id} · {new Date(d.created_at).toLocaleTimeString()}
                      </div>
                    </div>
                  </div>
                  <Badge variant="success" size="sm">
                    <span className="dot-indicator dot-teal" style={{ marginRight: '4px' }} />
                    {d.status}
                  </Badge>
                </div>
              ))}
            </div>
          )}
        </CardContent>
      </Card>
    </div>
  );
}
