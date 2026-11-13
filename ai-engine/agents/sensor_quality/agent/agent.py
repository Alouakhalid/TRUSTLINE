"""CrewAI Sensor Quality Agent factory and crew runner."""
import os
from typing import Optional, Dict, Any
from crewai import Agent, Crew, Process, LLM
from .prompts import (
    SENSOR_QUALITY_AGENT_ROLE,
    SENSOR_QUALITY_AGENT_GOAL,
    SENSOR_QUALITY_AGENT_BACKSTORY
)
from .tasks import create_sensor_quality_task
from ..tools.crewai_tools import get_crewai_tools
from ..config.settings import get_settings

def build_groq_llm() -> Optional[Any]:
    cfg = get_settings()
    api_key = cfg.groq_api_key or os.environ.get("GROQ_API_KEY", "")
    if not api_key:
        return None
    try:
        model_str = f"groq/{cfg.groq_model}"
        return LLM(model=model_str, api_key=api_key, temperature=0.1)
    except Exception:
        try:
            from langchain_groq import ChatGroq
            return ChatGroq(groq_api_key=api_key, model_name=cfg.groq_model, temperature=0.1)
        except Exception:
            return None

def create_sensor_quality_agent(llm: Optional[Any] = None) -> Agent:
    configured_llm = llm or build_groq_llm()
    tools = get_crewai_tools()

    agent_kwargs: Dict[str, Any] = {
        "role": SENSOR_QUALITY_AGENT_ROLE,
        "goal": SENSOR_QUALITY_AGENT_GOAL,
        "backstory": SENSOR_QUALITY_AGENT_BACKSTORY,
        "tools": tools,
        "verbose": False,
        "allow_delegation": False
    }

    if configured_llm is not None:
        agent_kwargs["llm"] = configured_llm

    return Agent(**agent_kwargs)

def run_sensor_quality_crew(
    astronaut_id: str,
    session_id: str,
    agent: Optional[Agent] = None
) -> str:
    assigned_agent = agent or create_sensor_quality_agent()
    task = create_sensor_quality_task(assigned_agent, astronaut_id, session_id)

    crew = Crew(
        agents=[assigned_agent],
        tasks=[task],
        process=Process.sequential,
        verbose=False
    )

    result = crew.kickoff()
    return str(result)

def generate_llm_briefing(
    astronaut_id: str,
    session_id: str,
    overall_quality_str: str,
    sensor_summaries_str: str,
    router: Optional[Any] = None
) -> Optional[str]:
    cfg = get_settings()
    api_key = cfg.groq_api_key or os.environ.get("GROQ_API_KEY", "")
    from hybrid_ai import HybridAIRouter, GroqProvider, ProviderRequest, TaskCategory
    r = router
    if r is None:
        if not api_key:
            return None
        groq_p = GroqProvider(api_key=api_key, model=cfg.groq_model, timeout=20.0)
        r = HybridAIRouter(groq_provider=groq_p)

    try:
        prompt = (
            f"You are the TRUSTLINE Sensor Quality Specialist. "
            f"Review this deterministic physiological sensor quality assessment for Astronaut {astronaut_id} (Session {session_id}):\n\n"
            f"Overall Status: {overall_quality_str}\n"
            f"Sensor Metrics:\n{sensor_summaries_str}\n\n"
            f"Provide a concise, 3-paragraph executive briefing for the Personal Health Agent. "
            f"1. Overall telemetry status and telemetry pass/fail decision.\n"
            f"2. Sensor-specific findings and physical causes of flagged issues.\n"
            f"3. Recommended downstream actions (e.g. signal filtering, sensor recalibration)."
        )
        req = ProviderRequest(
            task_category=TaskCategory.SENSOR_QUALITY_BRIEFING,
            prompt=prompt,
            temperature=0.2,
            max_tokens=600,
            timeout_seconds=20.0
        )
        resp = r.route_request(req)
        return resp.content
    except Exception as exc:
        return f"Briefing generation error: {str(exc)}"
