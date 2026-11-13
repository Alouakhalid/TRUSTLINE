"""Structured final assessment schema produced by the TRUSTLINE Supervisor Agent."""
from datetime import datetime
from enum import Enum
from typing import Dict, List, Optional, Any
from pydantic import BaseModel, Field

class WorkflowCompletionStatus(str, Enum):
    """Workflow completion status categories."""
    COMPLETED = "COMPLETED"
    PARTIALLY_COMPLETED = "PARTIALLY_COMPLETED"
    FAILED = "FAILED"

class AgentExecutionState(str, Enum):
    """Execution state for each integrated sub-agent."""
    SUCCESS = "SUCCESS"
    PARTIAL = "PARTIAL"
    SKIPPED = "SKIPPED"
    FAILED = "FAILED"

class AgentExecutionStatus(BaseModel):
    """Execution telemetry and outcome for a single agent."""
    agent_name: str
    status: AgentExecutionState
    execution_time_ms: float = Field(default=0.0)
    error_message: Optional[str] = None
    warnings: List[str] = Field(default_factory=list)

class EvidenceRegistryItem(BaseModel):
    """Unified cross-agent evidence item tracked in supervisor evidence registry."""
    evidence_id: str
    source_agent: str
    domain: str
    metric_name: str
    observed_value: Any
    validity_status: str
    is_quarantined: bool = False
    quarantine_reason: Optional[str] = None
    provenance: str

class CoverageSummary(BaseModel):
    """Coverage completeness across physiological and operational domains."""
    total_domains: int = Field(default=10)
    evaluated_domains: List[str] = Field(default_factory=list)
    unevaluated_domains: List[str] = Field(default_factory=list)
    partially_evaluated_domains: List[str] = Field(default_factory=list)
    domain_coverage_ratio: float = Field(default=0.0)
    coverage_status: str = Field(default="INSUFFICIENT")

class WorkflowTimingBreakdown(BaseModel):
    """Fine-grained execution timing breakdown across workflow orchestrator and subagents."""
    workflow_total_execution_time_ms: float = Field(default=0.0)
    supervisor_overhead_time_ms: float = Field(default=0.0)
    sensor_quality_execution_time_ms: float = Field(default=0.0)
    personal_health_execution_time_ms: float = Field(default=0.0)
    medical_rag_execution_time_ms: float = Field(default=0.0)
    risk_assessment_execution_time_ms: float = Field(default=0.0)
    evidence_validation_time_ms: float = Field(default=0.0)
    final_synthesis_time_ms: float = Field(default=0.0)
    persistence_time_ms: float = Field(default=0.0)
    measured_supervisor_overhead_ms: float = Field(default=0.0)

class FinalSupervisorAssessment(BaseModel):
    """Comprehensive final structured assessment synthesized by Supervisor for clinical systems and mission log."""
    assessment_id: str
    astronaut_id: str
    session_id: str
    workflow_id: str
    generation_timestamp: datetime = Field(default_factory=datetime.utcnow)
    workflow_completion_status: WorkflowCompletionStatus
    agent_execution_statuses: Dict[str, AgentExecutionStatus] = Field(default_factory=dict)
    timing_breakdown: WorkflowTimingBreakdown = Field(default_factory=WorkflowTimingBreakdown)
    overall_assessment_status: str
    overall_risk: str
    overall_confidence: str
    escalation_state: str
    escalation_required: bool = False
    escalation_urgency: str = "NOMINAL"
    coverage_summary: CoverageSummary = Field(default_factory=CoverageSummary)
    sensor_quality_summary: Dict[str, Any] = Field(default_factory=dict)
    personal_health_summary: Dict[str, Any] = Field(default_factory=dict)
    medical_rag_summary: Dict[str, Any] = Field(default_factory=dict)
    risk_assessment_summary: Dict[str, Any] = Field(default_factory=dict)
    detected_concerns: List[Dict[str, Any]] = Field(default_factory=list)
    nominal_observations: List[Dict[str, Any]] = Field(default_factory=list)
    protective_factors: List[Dict[str, Any]] = Field(default_factory=list)
    uncertainties: List[str] = Field(default_factory=list)
    missing_information: List[str] = Field(default_factory=list)
    recommended_actions: List[Dict[str, Any]] = Field(default_factory=list)
    evidence_references: List[EvidenceRegistryItem] = Field(default_factory=list)
    provenance_chain: List[Dict[str, Any]] = Field(default_factory=list)
    executive_synthesis: Optional[str] = None
    astronaut_facing_response: str
