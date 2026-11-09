"""Schemas defining deterministic risk rules, classifications, and rule outcomes."""
from enum import Enum
from typing import Dict, List, Optional, Any, Callable
from pydantic import BaseModel, Field
from .evidence import RiskDomain

class RiskLevel(str, Enum):
    """Categorical risk severity levels for individual domains and overall status."""
    UNKNOWN = "UNKNOWN"
    INSUFFICIENT_DATA = "INSUFFICIENT_DATA"
    LOW = "LOW"
    MODERATE = "MODERATE"
    HIGH = "HIGH"
    CRITICAL = "CRITICAL"

class RiskConfidence(str, Enum):
    """Categorical confidence in risk evaluation based on evidence completeness and sensor quality."""
    HIGH = "HIGH"
    MODERATE = "MODERATE"
    LOW = "LOW"
    UNDETERMINED = "UNDETERMINED"

class EscalationState(str, Enum):
    """Deterministic 6-state safety machine governing medical operational escalation."""
    NO_TRIGGER_DETECTED = "NO_TRIGGER_DETECTED"
    INSUFFICIENT_DATA = "INSUFFICIENT_DATA"
    ASSESSMENT_FAILED = "ASSESSMENT_FAILED"
    REVIEW_REQUIRED = "REVIEW_REQUIRED"
    ESCALATION_RECOMMENDED = "ESCALATION_RECOMMENDED"
    ESCALATION_REQUIRED = "ESCALATION_REQUIRED"

class EscalationDestination(str, Enum):
    """Authorized destination entities for operational escalation and briefings."""
    ASTRONAUT_SELF_MONITORING = "ASTRONAUT_SELF_MONITORING"
    FLIGHT_SURGEON = "FLIGHT_SURGEON"
    MISSION_CONTROL = "MISSION_CONTROL"
    EMERGENCY_MEDICAL_RESPONSE = "EMERGENCY_MEDICAL_RESPONSE"

class RiskRule(BaseModel):
    """Configurable, scientifically traceable rule definition for deterministic risk evaluation."""
    rule_id: str = Field(..., description="Unique immutable rule identifier e.g. RR-CARDIO-001")
    rule_name: str = Field(..., description="Descriptive clinical or operational title")
    domain: RiskDomain = Field(..., description="Target risk domain")
    required_variables: List[str] = Field(..., description="Evidence metrics required to evaluate rule")
    required_quality_conditions: List[str] = Field(default_factory=list, description="Sensor quality prerequisites")
    threshold_condition: str = Field(..., description="Mathematical or logical condition specification")
    risk_level: RiskLevel = Field(..., description="Assigned risk level when condition is satisfied")
    rule_source: str = Field(..., description="Traceable protocol or standards citation e.g. NASA-STD-3001")
    source_version: str = Field(..., description="Version of source document")
    applicable_mission_context: List[str] = Field(default_factory=list, description="Mission phases where rule applies")
    intended_scope: str = Field(..., description="Clinical or operational boundary of applicability")
    limitations: str = Field(..., description="Known scientific or observational boundaries")
    last_verification_date: str = Field(..., description="ISO date of clinical engineering validation")
    suggested_escalation: EscalationState = Field(default=EscalationState.NO_TRIGGER_DETECTED)
    suggested_destination: EscalationDestination = Field(default=EscalationDestination.FLIGHT_SURGEON)
    recommended_action: Optional[str] = Field(default=None, description="Predefined clinical directive")

class TriggeredRuleDetail(BaseModel):
    """Record of an explicit rule condition satisfied during evaluation."""
    rule_id: str = Field(..., description="Identifier of the triggered rule")
    rule_name: str = Field(..., description="Title of the triggered rule")
    domain: RiskDomain = Field(..., description="Associated risk domain")
    risk_level: RiskLevel = Field(..., description="Assigned risk severity")
    supporting_evidence_ids: List[str] = Field(default_factory=list, description="Evidence IDs establishing condition")
    rationale: str = Field(..., description="Factual derivation of why condition was met")
    suggested_escalation: EscalationState = Field(..., description="Recommended escalation level")
    rule_source: str = Field(..., description="Authoritative reference backing the rule")

class NonTriggeredRuleDetail(BaseModel):
    """Record of an evaluated rule whose conditions were not satisfied."""
    rule_id: str = Field(..., description="Identifier of evaluated rule")
    rule_name: str = Field(..., description="Title of evaluated rule")
    domain: RiskDomain = Field(..., description="Associated risk domain")
    evaluated_variables: List[str] = Field(default_factory=list, description="Observed variables tested")
    evaluation_reason: str = Field(..., description="Reason rule did not trigger e.g. within normal limits")
