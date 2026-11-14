import { useEffect, useRef, useCallback, useState } from 'react';
import { useAuthStore } from '@/features/auth/stores/auth-store';

type WSStatus = 'connecting' | 'connected' | 'disconnected' | 'error';

interface UseWebSocketOptions {
  astronautId: string;
  enabled?: boolean;
  onMessage?: (data: Record<string, unknown>) => void;
  reconnectInterval?: number;
  maxReconnectAttempts?: number;
  pingInterval?: number;
}

export function useWebSocket({
  astronautId,
  enabled = true,
  onMessage,
  reconnectInterval = 3000,
  maxReconnectAttempts = 10,
  pingInterval = 25000,
}: UseWebSocketOptions) {
  const { token } = useAuthStore();
  const wsRef = useRef<WebSocket | null>(null);
  const pingTimerRef = useRef<ReturnType<typeof setInterval> | null>(null);
  const reconnectCountRef = useRef(0);
  const reconnectTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  const [status, setStatus] = useState<WSStatus>('disconnected');
  const [lastPacketTime, setLastPacketTime] = useState<number | null>(null);
  const onMessageRef = useRef(onMessage);
  onMessageRef.current = onMessage;

  const cleanup = useCallback(() => {
    if (pingTimerRef.current) {
      clearInterval(pingTimerRef.current);
      pingTimerRef.current = null;
    }
    if (reconnectTimerRef.current) {
      clearTimeout(reconnectTimerRef.current);
      reconnectTimerRef.current = null;
    }
    if (wsRef.current) {
      wsRef.current.onopen = null;
      wsRef.current.onclose = null;
      wsRef.current.onmessage = null;
      wsRef.current.onerror = null;
      if (wsRef.current.readyState === WebSocket.OPEN || wsRef.current.readyState === WebSocket.CONNECTING) {
        wsRef.current.close(1000);
      }
      wsRef.current = null;
    }
  }, []);

  const connect = useCallback(() => {
    if (!token || !enabled || !astronautId) return;
    cleanup();

    const protocol = window.location.protocol === 'https:' ? 'wss' : 'ws';
    const url = `${protocol}://${window.location.host}/ws/telemetry/${astronautId}?token=${encodeURIComponent(token)}`;

    setStatus('connecting');
    const ws = new WebSocket(url);
    wsRef.current = ws;

    ws.onopen = () => {
      setStatus('connected');
      reconnectCountRef.current = 0;

      pingTimerRef.current = setInterval(() => {
        if (ws.readyState === WebSocket.OPEN) {
          ws.send('ping');
        }
      }, pingInterval);
    };

    ws.onmessage = (event) => {
      try {
        const data = JSON.parse(event.data);
        if (data.type === 'pong') return;
        setLastPacketTime(Date.now());
        onMessageRef.current?.(data);
      } catch {
        /* ignore non-JSON frames */
      }
    };

    ws.onerror = () => {
      setStatus('error');
    };

    ws.onclose = (event) => {
      setStatus('disconnected');
      if (pingTimerRef.current) {
        clearInterval(pingTimerRef.current);
        pingTimerRef.current = null;
      }

      if (event.code !== 1000 && reconnectCountRef.current < maxReconnectAttempts) {
        const jitter = Math.random() * 0.5 + 0.75;
        const delay = reconnectInterval * Math.pow(1.5, reconnectCountRef.current) * jitter;
        reconnectCountRef.current++;
        reconnectTimerRef.current = setTimeout(connect, Math.min(delay, 30000));
      }
    };
  }, [token, enabled, astronautId, cleanup, reconnectInterval, maxReconnectAttempts, pingInterval]);

  useEffect(() => {
    connect();
    return cleanup;
  }, [connect, cleanup]);

  const send = useCallback((data: Record<string, unknown>) => {
    if (wsRef.current?.readyState === WebSocket.OPEN) {
      wsRef.current.send(JSON.stringify(data));
    }
  }, []);

  return { status, lastPacketTime, send };
}
