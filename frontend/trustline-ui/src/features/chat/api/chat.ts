import { api } from '@/shared/lib/api-client';

export async function fetchSessions(params?: { q?: string; session_status?: string; limit?: number }) {
  return api.listSessions(params);
}

export async function createNewSession(title = 'New Chat') {
  return api.createSession(title);
}

export async function removeSession(sessionId: string) {
  return api.deleteSession(sessionId);
}

export async function fetchMessages(sessionId: string) {
  return api.getMessages(sessionId);
}

export async function postMessage(sessionId: string, content: string, file?: File) {
  if (file) {
    const formData = new FormData();
    if (content) formData.append('content', content);
    formData.append('file', file);
    return api.sendMessage(sessionId, formData);
  }
  return api.sendMessage(sessionId, content);
}

export async function triggerAssessment(astronautId: string, textQuery: string, sessionId?: string) {
  return api.runAssessment({
    astronaut_id: astronautId,
    text_query: textQuery,
    session_id: sessionId,
    mission_context: {
      flight_phase: 'DEEP_SPACE_TRANSIT',
      cabin_pressure_kpa: 101.3,
    },
  });
}
