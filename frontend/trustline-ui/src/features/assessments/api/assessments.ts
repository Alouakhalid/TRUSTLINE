import { api } from '@/shared/lib/api-client';

export async function listAssessments(astronautId?: string, limit = 50) {
  return api.listAssessments(astronautId, limit);
}

export async function getAssessmentDetail(assessmentId: string) {
  return api.getAssessment(assessmentId);
}

export async function runNewAssessment(
  astronautId: string,
  textQuery: string,
  sessionId?: string,
) {
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
