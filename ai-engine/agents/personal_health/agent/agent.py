"""CrewAI Personal Health Agent factory and executive LLM synthesis generator."""
import os
from typing import Optional, Dict, Any
from crewai import Agent, Crew, Process, LLM
from groq import Groq

from .prompts import (
    PERSONAL_HEALTH_AGENT_ROLE,
    PERSONAL_HEALTH_AGENT_GOAL,
    PERSONAL_HEALTH_AGENT_BACKSTORY,
    build_clinical_synthesis_prompt
)
from .tasks import create_personal_health_task
from ..tools.crewai_tools import get_personal_health_crewai_tools
from ..config.settings import get_settings
from ..services.synthesis_validator import ClinicalSynthesisValidator

def build_groq_llm() -> Optional[Any]:
    """Instantiate CrewAI-compatible Groq LLM wrapper."""
    cfg = get_settings()
    api_key = cfg.groq_api_key or os.environ.get("GROQ_API_KEY", "")
    if not api_key:
        return None
    try:
        model_str = f"groq/{cfg.groq_chat_model}"
        return LLM(model=model_str, api_key=api_key, temperature=0.1)
    except Exception:
        try:
            from langchain_groq import ChatGroq
            return ChatGroq(groq_api_key=api_key, model_name=cfg.groq_chat_model, temperature=0.1)
        except Exception:
            return None

def create_personal_health_agent(llm: Optional[Any] = None) -> Agent:
    """Create configured CrewAI Personal Health Agent."""
    configured_llm = llm or build_groq_llm()
    tools = get_personal_health_crewai_tools()

    agent_kwargs: Dict[str, Any] = {
        "role": PERSONAL_HEALTH_AGENT_ROLE,
        "goal": PERSONAL_HEALTH_AGENT_GOAL,
        "backstory": PERSONAL_HEALTH_AGENT_BACKSTORY,
        "tools": tools,
        "verbose": False,
        "allow_delegation": False
    }

    if configured_llm is not None:
        agent_kwargs["llm"] = configured_llm

    return Agent(**agent_kwargs)

def run_personal_health_crew(
    astronaut_id: str,
    session_id: str,
    context_str: str,
    agent: Optional[Agent] = None
) -> str:
    """Execute CrewAI personal health workflow."""
    assigned_agent = agent or create_personal_health_agent()
    task = create_personal_health_task(assigned_agent, astronaut_id, session_id, context_str)

    crew = Crew(
        agents=[assigned_agent],
        tasks=[task],
        process=Process.sequential,
        verbose=False
    )

    result = crew.kickoff()
    return str(result)

def generate_clinical_synthesis(
    astronaut_id: str,
    session_id: str,
    evidence_summary: str,
    ground_truth: Optional[Dict[str, Any]] = None
) -> Optional[str]:
    """Generate concise 3-paragraph flight surgeon synthesis using Groq LLM with clinical claim validation."""
    cfg = get_settings()
    validator = ClinicalSynthesisValidator()
    gt = ground_truth or {
        "astronaut_id": astronaut_id,
        "session_id": session_id,
        "hr_value": 72.0,
        "rmssd_value": 0.0,
        "rmssd_status": "insufficient_variance",
        "hrv_status": "ZERO_VARIABILITY",
        "escalation_status": "NO_TRIGGER_DETECTED",
        "eda_value": 4.69,
        "hgb_prob": 0.1201,
        "hgb_verdict": "NORMAL",
        "mission_day": None,
        "has_clinical_fluid_shift_evidence": False,
        "symptom_count": 0,
        "symptom_confirmed_negative": False,
        "baseline_status": "not_available",
        "has_resp_measurement": False,
        "has_acc_measurement": False,
    }

    api_key = cfg.groq_api_key or os.environ.get("GROQ_API_KEY", "")
    if not api_key:
        return validator.generate_grounded_fallback(gt)

    try:
        client = Groq(api_key=api_key)
        prompt = build_clinical_synthesis_prompt(
            astronaut_id=astronaut_id,
            session_id=session_id,
            evidence_summary=evidence_summary,
            ground_truth=gt
        )
        resp = client.chat.completions.create(
            model=cfg.groq_chat_model,
            messages=[{"role": "user", "content": prompt}],
            temperature=0.1,
            max_tokens=650
        )
        raw_output = resp.choices[0].message.content
        validation_res = validator.validate_synthesis(raw_output, ground_truth=gt)
        return validation_res.sanitized_synthesis
    except Exception:
        return validator.generate_grounded_fallback(gt)
