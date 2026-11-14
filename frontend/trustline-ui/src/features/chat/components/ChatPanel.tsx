import { useState, useRef, useEffect, KeyboardEvent, ChangeEvent } from 'react';
import { Plus, Trash2, SendHorizontal, Loader2, MessageSquare, Paperclip, X, FileText } from 'lucide-react';
import { Button } from '@/shared/components/Button';
import { Badge } from '@/shared/components/Badge';
import { ProviderStatus } from './ProviderStatus';
import { ProviderSelector } from './ProviderSelector';
import { ChatMessage } from './ChatMessage';
import { useChat } from '../hooks/useChat';

export function ChatPanel() {
  const {
    sessions, activeSessionId, messages,
    isLoadingSessions, isLoadingMessages, isSending, isAssessing, latestTrace,
    selectSession, createSession, deleteSession, sendMessage,
  } = useChat();

  const [input, setInput] = useState('');
  const [selectedFile, setSelectedFile] = useState<File | null>(null);
  const messagesEndRef = useRef<HTMLDivElement>(null);
  const fileInputRef = useRef<HTMLInputElement>(null);

  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [messages]);

  const handleSend = () => {
    if ((!input.trim() && !selectedFile) || isSending || isAssessing) return;
    sendMessage(input, selectedFile || undefined);
    setInput('');
    setSelectedFile(null);
    if (fileInputRef.current) fileInputRef.current.value = '';
  };

  const handleKeyDown = (e: KeyboardEvent<HTMLTextAreaElement>) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      handleSend();
    }
  };

  const handleFileChange = (e: ChangeEvent<HTMLInputElement>) => {
    if (e.target.files && e.target.files[0]) {
      setSelectedFile(e.target.files[0]);
    }
  };

  return (
    <div className="chat-container">
      {/* Sidebar */}
      <div className="chat-sidebar">
        <div className="chat-sidebar-header">
          <Button variant="primary" size="sm" icon={<Plus size={14} />} onClick={() => createSession()} style={{ width: '100%' }}>
            New Chat
          </Button>
          <div style={{ marginTop: '8px' }}>
            <ProviderStatus />
          </div>
        </div>
        <div className="chat-session-list">
          {isLoadingSessions ? (
            <p style={{ fontSize: '12px', color: 'var(--text-muted)', padding: '12px' }}>Loading...</p>
          ) : sessions.length === 0 ? (
            <p style={{ fontSize: '12px', color: 'var(--text-muted)', padding: '12px' }}>No sessions yet</p>
          ) : (
            sessions.map((s) => (
              <div
                key={s.id}
                className={`chat-session-item ${activeSessionId === s.id ? 'chat-session-item--active' : ''}`}
                onClick={() => selectSession(s.id)}
                role="button"
                tabIndex={0}
                onKeyDown={(e) => e.key === 'Enter' && selectSession(s.id)}
              >
                <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                  <span className="chat-session-title">{s.title}</span>
                  <button
                    onClick={(e) => { e.stopPropagation(); deleteSession(s.id); }}
                    style={{ background: 'none', border: 'none', color: 'var(--text-muted)', cursor: 'pointer', padding: '4px' }}
                    aria-label={`Delete ${s.title}`}
                    type="button"
                  >
                    <Trash2 size={12} />
                  </button>
                </div>
                {s.latest_preview && <div className="chat-session-preview">{s.latest_preview}</div>}
              </div>
            ))
          )}
        </div>
      </div>

      {/* Main chat area */}
      <div className="chat-main">
        <ProviderSelector trace={latestTrace} />
        {!activeSessionId ? (
          <div className="chat-empty">
            <MessageSquare size={44} style={{ color: 'var(--color-accent)' }} />
            <p style={{ fontSize: '18px', fontWeight: 600, color: 'var(--text-bright)' }}>AI Medical Intelligence Chat</p>
            <p style={{ fontSize: '13px', color: 'var(--text-secondary)', maxWidth: '380px', textAlign: 'center' }}>
              Connect directly with the multi-agent clinical supervisor. Ask questions about mission health, symptoms, or upload medical records (PDF, DOCX, scan images) for instant OCR analysis.
            </p>
            <Button
              variant="primary"
              size="md"
              icon={<Plus size={16} />}
              onClick={() => createSession('Mission Medical Log')}
              style={{ marginTop: '12px' }}
            >
              Start New Conversation
            </Button>
          </div>
        ) : (
          <>
            <div className="chat-messages">
              {isLoadingMessages ? (
                <p style={{ textAlign: 'center', color: 'var(--text-muted)' }}>Loading messages...</p>
              ) : messages.length === 0 ? (
                <div className="chat-empty">
                  <p>No messages yet. Send a message or attach a medical document (PDF, DOCX, Image) to begin.</p>
                </div>
              ) : (
                messages.map((m) => <ChatMessage key={m.id} message={m} />)
              )}
              {(isSending || isAssessing) && (
                <div className="chat-message chat-message--agent">
                  <div className="chat-message-avatar">
                    <Loader2 size={16} className="btn-spinner" />
                  </div>
                  <div className="chat-message-bubble" style={{ color: 'var(--color-secondary-ink)', display: 'flex', alignItems: 'center', gap: '8px' }}>
                    <span className="dot-indicator dot-teal" />
                    <span>
                      {selectedFile
                        ? 'Extracting clinical text via OCR and orchestrating LangGraph Supervisor (SQA, PHA, Medical RAG, RAA)...'
                        : 'LangGraph Supervisor orchestrating subagents (SQA, PHA, Medical RAG, RAA)...'}
                    </span>
                  </div>
                </div>
              )}
              <div ref={messagesEndRef} />
            </div>

            {/* Input area with file preview and attachment button */}
            <div className="chat-input-area" style={{ display: 'flex', flexDirection: 'column', gap: '8px' }}>
              {selectedFile && (
                <div
                  style={{
                    display: 'flex',
                    alignItems: 'center',
                    gap: '10px',
                    padding: '6px 12px',
                    background: 'var(--color-ground-secondary)',
                    border: '1px solid var(--color-hairline)',
                    borderLeft: '3px solid var(--color-teal)',
                    borderRadius: 'var(--radius-xs)',
                    width: '100%',
                  }}
                >
                  <FileText size={15} style={{ color: 'var(--color-teal)', flexShrink: 0 }} />
                  <span style={{ fontSize: '12px', color: 'var(--color-ink)', fontWeight: 500, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
                    {selectedFile.name}
                  </span>
                  <span style={{ fontSize: '11px', color: 'var(--color-muted)', fontFamily: 'var(--font-mono)' }}>
                    ({(selectedFile.size / 1024).toFixed(1)} KB)
                  </span>
                  <Badge variant="info" size="sm" style={{ marginLeft: '4px' }}>
                    OCR READY
                  </Badge>
                  <button
                    type="button"
                    onClick={() => {
                      setSelectedFile(null);
                      if (fileInputRef.current) fileInputRef.current.value = '';
                    }}
                    style={{
                      background: 'none',
                      border: 'none',
                      color: 'var(--color-muted)',
                      cursor: 'pointer',
                      marginLeft: 'auto',
                      padding: '2px',
                      display: 'flex',
                      alignItems: 'center',
                    }}
                    title="Remove attachment"
                  >
                    <X size={14} />
                  </button>
                </div>
              )}

              <div style={{ display: 'flex', alignItems: 'center', gap: '8px', width: '100%' }}>
                <input
                  type="file"
                  ref={fileInputRef}
                  onChange={handleFileChange}
                  accept=".pdf,.docx,.png,.jpg,.jpeg,.webp"
                  style={{ display: 'none' }}
                />
                <Button
                  type="button"
                  variant="ghost"
                  size="md"
                  icon={<Paperclip size={16} />}
                  onClick={() => fileInputRef.current?.click()}
                  disabled={isSending || isAssessing}
                  title="Attach clinical document (PDF, DOCX, PNG, JPG)"
                  style={{
                    color: selectedFile ? 'var(--color-teal)' : 'var(--color-ink-secondary)',
                    border: selectedFile ? '1px solid var(--color-teal)' : '1px solid var(--color-hairline)',
                    padding: '8px 10px',
                  }}
                />
                <textarea
                  value={input}
                  onChange={(e) => setInput(e.target.value)}
                  onKeyDown={handleKeyDown}
                  placeholder={selectedFile ? 'Optional: add query about this document...' : 'Ask about astronaut health, request an assessment, or attach medical records...'}
                  rows={1}
                  disabled={isSending || isAssessing}
                  style={{ flex: 1 }}
                />
                <Button
                  variant="primary"
                  size="md"
                  onClick={handleSend}
                  disabled={(!input.trim() && !selectedFile) || isSending || isAssessing}
                  icon={isSending ? <Loader2 size={16} className="btn-spinner" /> : <SendHorizontal size={16} />}
                  aria-label="Send message"
                />
              </div>
            </div>
          </>
        )}
      </div>
    </div>
  );
}
