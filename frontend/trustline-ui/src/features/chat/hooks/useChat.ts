import { useState, useCallback, useEffect, useRef } from 'react';
import { useAuthStore } from '@/features/auth/stores/auth-store';
import { fetchSessions, createNewSession, removeSession, fetchMessages, postMessage, triggerAssessment } from '../api/chat';

interface ChatSession {
  id: string;
  title: string;
  status: string;
  message_count?: number;
  latest_preview?: string;
  created_at: string;
}

interface ChatMessage {
  id: string;
  session_id: string;
  sender: string;
  content: string;
  agent: string | null;
  processing_status: string;
  citations: unknown[];
  created_at: string;
}

export function useChat() {
  const { astronautId } = useAuthStore();
  const [sessions, setSessions] = useState<ChatSession[]>([]);
  const [activeSessionId, setActiveSessionId] = useState<string | null>(null);
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [isLoadingSessions, setIsLoadingSessions] = useState(false);
  const [isLoadingMessages, setIsLoadingMessages] = useState(false);
  const [isSending, setIsSending] = useState(false);
  const [isAssessing, setIsAssessing] = useState(false);
  const [latestTrace, setLatestTrace] = useState<any>(null);
  const pollingRef = useRef<ReturnType<typeof setTimeout> | null>(null);

  const loadMessages = useCallback(async (sessionId: string) => {
    setIsLoadingMessages(true);
    try {
      const data = await fetchMessages(sessionId);
      setMessages(data);
    } catch (err) {
      console.error('Failed to load messages:', err);
    } finally {
      setIsLoadingMessages(false);
    }
  }, []);

  const loadSessions = useCallback(async () => {
    setIsLoadingSessions(true);
    try {
      const data = await fetchSessions({ session_status: 'ACTIVE', limit: 50 });
      const sessionList = data as unknown as ChatSession[];
      setSessions(sessionList);
      if (sessionList.length > 0 && !activeSessionId) {
        setActiveSessionId(sessionList[0].id);
        await loadMessages(sessionList[0].id);
      }
    } catch (err) {
      console.error('Failed to load sessions:', err);
    } finally {
      setIsLoadingSessions(false);
    }
  }, [activeSessionId, loadMessages]);

  const selectSession = useCallback(async (sessionId: string) => {
    setActiveSessionId(sessionId);
    await loadMessages(sessionId);
  }, [loadMessages]);

  const createSession = useCallback(async (title = 'New Chat') => {
    try {
      const session = await createNewSession(title) as unknown as ChatSession;
      setSessions((prev) => [session, ...prev]);
      setActiveSessionId(session.id);
      setMessages([]);
      return session;
    } catch (err) {
      console.error('Failed to create session:', err);
      throw err;
    }
  }, []);

  const deleteSession = useCallback(async (sessionId: string) => {
    try {
      await removeSession(sessionId);
      setSessions((prev) => prev.filter((s) => s.id !== sessionId));
      if (activeSessionId === sessionId) {
        setActiveSessionId(null);
        setMessages([]);
      }
    } catch (err) {
      console.error('Failed to delete session:', err);
    }
  }, [activeSessionId]);

  const pollForAgentResponse = useCallback((sessionId: string, initialCount: number) => {
    let attempts = 0;
    const maxAttempts = 15;

    const poll = async () => {
      attempts++;
      try {
        const data = await fetchMessages(sessionId);
        const agentMessages = data.filter((m) => m.sender === 'AGENT');
        if (agentMessages.length > 0 && data.length > initialCount) {
          setMessages(data);
          setIsAssessing(false);
          return;
        }
      } catch {
        /* continue polling */
      }

      if (attempts < maxAttempts) {
        pollingRef.current = setTimeout(poll, 2000);
      } else {
        setIsAssessing(false);
        if (sessionId === activeSessionId) {
          await loadMessages(sessionId);
        }
      }
    };

    pollingRef.current = setTimeout(poll, 2000);
  }, [activeSessionId, loadMessages]);

  const sendMessage = useCallback(async (content: string, file?: File) => {
    if (!activeSessionId || (!content.trim() && !file)) return;

    setIsSending(true);
    try {
      const result = await postMessage(activeSessionId, content, file);
      const userMsg = result.user_message as unknown as ChatMessage;
      const agentMsg = result.agent_message as unknown as ChatMessage;

      if (agentMsg && agentMsg.content) {
        setMessages((prev) => [...prev, userMsg, agentMsg]);
        if (result.assessment) {
          setLatestTrace(result.assessment);
        }
      } else {
        setMessages((prev) => [...prev, userMsg]);
        await loadMessages(activeSessionId);
      }
    } catch (err) {
      console.error('Failed to send message:', err);
    } finally {
      setIsSending(false);
      setIsAssessing(false);
    }
  }, [activeSessionId, loadMessages]);

  useEffect(() => {
    loadSessions();
  }, [loadSessions]);

  useEffect(() => {
    return () => {
      if (pollingRef.current) clearTimeout(pollingRef.current);
    };
  }, []);

  return {
    sessions,
    activeSessionId,
    messages,
    isLoadingSessions,
    isLoadingMessages,
    isSending,
    isAssessing,
    latestTrace,
    selectSession,
    createSession,
    deleteSession,
    sendMessage,
    refreshMessages: activeSessionId ? () => loadMessages(activeSessionId) : () => Promise.resolve(),
  };
}
