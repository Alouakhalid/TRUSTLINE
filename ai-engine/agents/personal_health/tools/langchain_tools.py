"""LangChain StructuredTool definitions for Personal Health Agent."""
from typing import List, Any
from langchain_core.tools import tool
from .crewai_tools import (
    query_health_profile_tool,
    run_stress_inference_tool,
    transcribe_groq_voice_tool,
    extract_symptom_report_tool,
    query_medical_rag_tool,
    get_personal_health_crewai_tools
)

def get_personal_health_langchain_tools() -> List[Any]:
    """Retrieve LangChain tool representations."""
    return get_personal_health_crewai_tools()
