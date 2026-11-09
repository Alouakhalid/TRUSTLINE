"""Conditional routing functions for the LangGraph Supervisor workflow."""
from typing import Dict, Any

def route_after_validation(state: Dict[str, Any]) -> str:
    """Route to evidence validation on critical validation failure, or proceed to sensor quality."""
    errors = state.get("errors") or []
    status = state.get("workflow_status")
    if errors or status == "FAILED":
        return "evidence_validation"
    return "sensor_quality"
