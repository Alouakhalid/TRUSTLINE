"""CrewAI task definitions for Personal Health Agent."""
from typing import Dict, Any
from crewai import Task, Agent

def create_personal_health_task(
    agent: Agent,
    astronaut_id: str,
    session_id: str,
    context_str: str
) -> Task:
    """Create clinical synthesis task for CrewAI agent."""
    description = (
        f"Perform an in-depth clinical health assessment for Astronaut {astronaut_id} (Session {session_id}).\n\n"
        f"Context & Extracted Findings:\n{context_str}\n\n"
        "Requirements:\n"
        "1. Synthesize physiological observations (HR, HRV, EDA, and other available telemetry), explicitly flagging zero or unvarying RMSSD as invalid for parasympathetic assessment and omitting unmeasured streams.\n"
        "2. Evaluate ML stress classification predictions strictly within WESAD benchmark boundaries.\n"
        "3. Review subjective symptom reports; lack of reported symptoms must not be stated as confirmed absence of symptoms.\n"
        "4. Correlate findings with retrieved aerospace medical literature and flight protocols.\n"
        "5. Document identified evidence conflicts, uncertainties, and missing information.\n"
        "6. Respect baseline_status (if not_available, do not compare or recommend session as personal baseline).\n"
        "7. Produce a structured, 3-paragraph executive clinical synthesis for the Supervisor Agent without diagnosing disease or prescribing treatment."
    )
    expected_output = (
        "An objective 3-paragraph executive clinical briefing summarizing telemetry state, "
        "autonomic arousal vs physical activity context, subjective symptom correlation, and recommended follow-up."
    )
    return Task(
        description=description,
        expected_output=expected_output,
        agent=agent
    )
