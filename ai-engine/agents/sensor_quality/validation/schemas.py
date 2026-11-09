"""Pydantic schemas and dataclasses for the Sensor Quality Validation Layer."""
from enum import Enum
from typing import Dict, List, Optional, Any
from pydantic import BaseModel, Field

class ValidationVerdict(str, Enum):
    PASS = "PASS"
    CONDITIONAL_PASS = "CONDITIONAL PASS"
    FAIL = "FAIL"
    INVALID = "INVALID"

class CheckStatus(str, Enum):
    PASSED = "PASSED"
    WARNING = "WARNING"
    FAILED = "FAILED"

class ValidationCheckResult(BaseModel):
    check_id: str = Field(..., description="Unique identifier for validation rule")
    category: str = Field(..., description="Validation category")
    target: str = Field(..., description="Target sensor or subsystem")
    status: CheckStatus = Field(..., description="Outcome of check")
    message: str = Field(..., description="Factual description of outcome")
    evidence: Dict[str, Any] = Field(default_factory=dict, description="Numerical or structured evidence")

class ScoreAuditRecord(BaseModel):
    sensor: str = Field(..., description="Sensor name or OVERALL")
    reported_score: float = Field(..., description="Score reported by agent")
    recalculated_score: float = Field(..., description="Independently reproduced score")
    delta: float = Field(..., description="Absolute discrepancy")
    is_match: bool = Field(..., description="Whether discrepancy is within float tolerance")
    component_breakdown: Dict[str, float] = Field(default_factory=dict)

class SensorValidationSummary(BaseModel):
    sensor: str = Field(..., description="Sensor name")
    quality_score: float = Field(..., description="Audited quality score")
    status: str = Field(...)
    recommendation: str = Field(...)
    critical_failure: bool = Field(...)
    issue_count: int = Field(..., ge=0)
    verdict: str = Field(...)
    notes: str = Field(default="")

class OverallValidationSummary(BaseModel):
    verdict: ValidationVerdict = Field(...)
    checks_run: int = Field(..., ge=0)
    checks_passed: int = Field(..., ge=0)
    checks_warned: int = Field(..., ge=0)
    checks_failed: int = Field(..., ge=0)
    critical_issues: List[str] = Field(default_factory=list)
    sensor_summaries: Dict[str, SensorValidationSummary] = Field(default_factory=dict)
    score_audits: List[ScoreAuditRecord] = Field(default_factory=list)
    temperature_investigation: Dict[str, Any] = Field(default_factory=dict)
    llm_consistency: Dict[str, Any] = Field(default_factory=dict)
