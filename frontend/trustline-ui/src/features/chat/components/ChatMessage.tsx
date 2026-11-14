import { useState } from 'react';
import { Bot, User, ShieldCheck, ChevronDown, ChevronUp, FileText, Paperclip } from 'lucide-react';
import { Badge } from '@/shared/components/Badge';

interface CitationData {
  evidence_id?: string;
  source_agent?: string;
  metric_name?: string;
  provenance?: string;
  observed_value?: unknown;
  type?: string;
  filename?: string;
  size_bytes?: number;
  records_count?: number;
}

interface ChatMessageData {
  id: string;
  sender: string;
  content: string;
  agent?: string | null;
  processing_status?: string;
  citations?: any[];
  created_at: string;
}

function renderFormattedText(text: string) {
  const lines = text.split('\n');
  const elements: React.ReactNode[] = [];
  let currentList: string[] = [];
  let currentTable: string[][] = [];

  const flushList = () => {
    if (currentList.length > 0) {
      elements.push(
        <ul key={`ul-${elements.length}`} style={{ margin: '6px 0 10px 18px', padding: 0 }}>
          {currentList.map((item, idx) => (
            <li key={idx} style={{ marginBottom: '4px', color: 'var(--color-ink)' }}>
              {renderInline(item)}
            </li>
          ))}
        </ul>
      );
      currentList = [];
    }
  };

  const flushTable = () => {
    if (currentTable.length > 0) {
      const header = currentTable[0];
      const rows = currentTable.slice(1).filter((r) => !r.every((c) => /^:?-+:?$/.test(c.trim())));
      elements.push(
        <div key={`table-${elements.length}`} style={{ overflowX: 'auto', margin: '10px 0 14px 0' }}>
          <table
            style={{
              width: '100%',
              borderCollapse: 'collapse',
              fontSize: '11.5px',
              fontFamily: 'var(--font-mono)',
              background: 'var(--color-ground-secondary)',
              border: '1px solid var(--color-hairline)',
              borderRadius: 'var(--radius-xs)',
            }}
          >
            <thead>
              <tr style={{ borderBottom: '1px solid var(--color-hairline)', background: 'rgba(237, 231, 220, 0.04)' }}>
                {header.map((col, idx) => (
                  <th key={idx} style={{ padding: '8px 10px', textAlign: 'left', fontWeight: 600, color: 'var(--color-secondary-ink)', textTransform: 'uppercase', fontSize: '10px', letterSpacing: '0.08em' }}>
                    {renderInline(col.trim())}
                  </th>
                ))}
              </tr>
            </thead>
            <tbody>
              {rows.map((row, rIdx) => (
                <tr key={rIdx} style={{ borderBottom: '1px solid rgba(237, 231, 220, 0.06)' }}>
                  {row.map((cell, cIdx) => (
                    <td key={cIdx} style={{ padding: '6px 10px', color: 'var(--color-ink)' }}>
                      {renderInline(cell.trim())}
                    </td>
                  ))}
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      );
      currentTable = [];
    }
  };

  const renderInline = (str: string) => {
    const parts: React.ReactNode[] = [];
    const regex = /(\*\*[^*]+\*\*|`[^`]+`|\*[^*]+\*)/g;
    let match: RegExpExecArray | null;
    let lastIndex = 0;
    let keyIdx = 0;

    while ((match = regex.exec(str)) !== null) {
      if (match.index > lastIndex) {
        parts.push(str.substring(lastIndex, match.index));
      }
      const token = match[0];
      if (token.startsWith('**') && token.endsWith('**')) {
        parts.push(
          <strong key={keyIdx++} style={{ color: 'var(--color-ink)', fontWeight: 600 }}>
            {token.slice(2, -2)}
          </strong>
        );
      } else if (token.startsWith('`') && token.endsWith('`')) {
        parts.push(
          <code
            key={keyIdx++}
            style={{
              padding: '1px 5px',
              borderRadius: '2px',
              background: 'rgba(237, 231, 220, 0.08)',
              fontFamily: 'var(--font-mono)',
              fontSize: '12px',
              color: 'var(--color-amber)',
            }}
          >
            {token.slice(1, -1)}
          </code>
        );
      } else if (token.startsWith('*') && token.endsWith('*')) {
        parts.push(
          <em key={keyIdx++} style={{ color: 'var(--color-secondary-ink)' }}>
            {token.slice(1, -1)}
          </em>
        );
      }
      lastIndex = regex.lastIndex;
    }

    if (lastIndex < str.length) {
      parts.push(str.substring(lastIndex));
    }

    return parts.length > 0 ? parts : str;
  };

  for (let i = 0; i < lines.length; i++) {
    const rawLine = lines[i].trim();
    if (!rawLine) {
      flushList();
      flushTable();
      continue;
    }

    // Markdown Table Line
    if (rawLine.startsWith('|') && rawLine.endsWith('|')) {
      flushList();
      const cells = rawLine.slice(1, -1).split('|');
      currentTable.push(cells);
      continue;
    } else {
      flushTable();
    }

    if (rawLine.startsWith('### ')) {
      flushList();
      elements.push(
        <div
          key={`h3-${i}`}
          style={{
            fontFamily: 'var(--font-heading)',
            fontSize: '13px',
            fontWeight: 700,
            letterSpacing: '-0.01em',
            color: 'var(--color-ink)',
            marginTop: '12px',
            marginBottom: '4px',
            borderBottom: '1px solid var(--color-hairline)',
            paddingBottom: '3px',
          }}
        >
          {renderInline(rawLine.replace(/^###\s+/, ''))}
        </div>
      );
    } else if (rawLine.startsWith('- ')) {
      currentList.push(rawLine.replace(/^- \s*/, ''));
    } else {
      flushList();
      elements.push(
        <p key={`p-${i}`} style={{ margin: '4px 0 6px 0', lineHeight: 1.55 }}>
          {renderInline(rawLine)}
        </p>
      );
    }
  }

  flushList();
  flushTable();
  return elements;
}

export function ChatMessage({ message }: { message: ChatMessageData }) {
  const [showCitations, setShowCitations] = useState(false);
  const isUser = message.sender === 'USER';
  const isAgent = message.sender === 'AGENT';

  const formatTime = (iso: string) => {
    try {
      return new Date(iso).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });
    } catch {
      return '';
    }
  };

  // Detect attachment in citations or content
  const attachmentCitation = message.citations?.find((c) => c.type === 'attachment');
  const hasAttachmentTag = message.content.includes('[Attached Document:');
  const attachmentMatch = message.content.match(/\[Attached Document:\s*([^\]]+)\]/);
  const attachedFilename = attachmentCitation?.filename || (attachmentMatch ? attachmentMatch[1] : null);

  // Clean user text if attachment tag is present
  const cleanedUserContent = message.content.replace(/\[Attached Document:[^\]]+\]\n*/g, '').trim();

  return (
    <div className={`chat-message ${isUser ? 'chat-message--user' : 'chat-message--agent'}`}>
      <div className="chat-message-avatar">
        {isUser ? <User size={16} /> : <Bot size={16} />}
      </div>
      <div style={{ maxWidth: '100%', minWidth: '240px' }}>
        <div className="chat-message-bubble">
          {/* User Attachment Banner */}
          {isUser && attachedFilename && (
            <div
              style={{
                display: 'flex',
                alignItems: 'center',
                gap: '8px',
                padding: '6px 10px',
                background: 'rgba(46, 107, 114, 0.14)',
                border: '1px solid var(--color-teal)',
                borderRadius: 'var(--radius-xs)',
                marginBottom: cleanedUserContent ? '8px' : '0',
              }}
            >
              <FileText size={15} style={{ color: 'var(--color-teal)', flexShrink: 0 }} />
              <div style={{ display: 'flex', flexDirection: 'column' }}>
                <span style={{ fontSize: '11px', fontWeight: 600, color: 'var(--color-ink)' }}>
                  {attachedFilename}
                </span>
                <span className="dark-label" style={{ fontSize: '9px', color: 'var(--color-teal)' }}>
                  [ OCR PROCESSED // CLINICAL INTAKE ]
                </span>
              </div>
              <Badge variant="info" size="sm" style={{ marginLeft: 'auto' }}>
                OCR
              </Badge>
            </div>
          )}

          {isAgent ? (
            renderFormattedText(message.content)
          ) : (
            cleanedUserContent ? <div>{cleanedUserContent}</div> : null
          )}

          {isAgent && message.citations && message.citations.length > 0 && (
            <div style={{ marginTop: '10px', paddingTop: '8px', borderTop: '1px solid var(--color-hairline)' }}>
              <button
                type="button"
                onClick={() => setShowCitations(!showCitations)}
                style={{
                  background: 'none',
                  border: 'none',
                  padding: 0,
                  cursor: 'pointer',
                  display: 'flex',
                  alignItems: 'center',
                  gap: '6px',
                  color: 'var(--color-teal)',
                  fontSize: '11px',
                  fontFamily: 'var(--font-mono)',
                }}
              >
                <ShieldCheck size={12} />
                <span>Verified Evidence & OCR Citations ({message.citations.length})</span>
                {showCitations ? <ChevronUp size={12} /> : <ChevronDown size={12} />}
              </button>
              {showCitations && (
                <div style={{ marginTop: '8px', display: 'flex', flexDirection: 'column', gap: '4px' }}>
                  {message.citations.map((c, idx) => (
                    <div
                      key={idx}
                      style={{
                        fontSize: '11px',
                        fontFamily: 'var(--font-mono)',
                        padding: '4px 8px',
                        background: 'rgba(46, 107, 114, 0.08)',
                        borderRadius: 'var(--radius-xs)',
                        display: 'flex',
                        justifyContent: 'space-between',
                      }}
                    >
                      <span style={{ color: 'var(--color-teal)' }}>{c.source_agent || 'SUPERVISOR'}</span>
                      <span style={{ color: 'var(--color-ink)' }}>{c.metric_name || c.evidence_id}</span>
                    </div>
                  ))}
                </div>
              )}
            </div>
          )}
        </div>
        <div className="chat-message-time">
          {isAgent ? 'LangGraph Supervisor' : isUser ? 'You' : message.sender} · {formatTime(message.created_at)}
        </div>
      </div>
    </div>
  );
}
