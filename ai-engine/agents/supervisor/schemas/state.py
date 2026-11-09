"""Typed state dictionary representation for LangGraph Supervisor workflow."""
from typing import Dict, List, Optional, Any, TypedDict

class SupervisorMultiAgentState(TypedDict, total=False):
    """Shared state dictionary representing data flowing across the LangGraph Supervisor pipeline."""
    astronaut_id: str
    session_id: str
    request_id: str
    workflow_id: str
    incoming_request: Dict[str, Any]
    sensor_data: Optional[Dict[str, Any]]
    manifest_path: Optional[str]
    astronaut_profile: Optional[Dict[str, Any]]
    reported_symptoms: List[Dict[str, Any]]
    reported_symptoms_text: Optional[str]
    reported_symptoms_voice_path: Optional[str]
    voice_language: Optional[str]
    medical_documents: List[Dict[str, Any]]
    confirmed_medical_records: List[Dict[str, Any]]
    mission_context: Optional[Dict[str, Any]]
    sensor_quality_result: Optional[Dict[str, Any]]
    personal_health_result: Optional[Dict[str, Any]]
    risk_assessment_result: Optional[Dict[str, Any]]
    evidence_registry: List[Dict[str, Any]]
    execution_status: str
    current_step: str
    workflow_status: str
    agent_execution_status: Dict[str, Dict[str, Any]]
    errors: List[str]
    warnings: List[str]
    missing_data: List[str]
    final_assessment: Optional[Dict[str, Any]]
    final_response: Optional[str]
    timestamps: Dict[str, str]
    perf_timestamps: Dict[str, float]
    durations_ms: Dict[str, float]
    audit_metadata: Dict[str, Any]
    requires_human_review: Optional[bool]
    overall_risk: Optional[str]
    escalation_state: Optional[str]
