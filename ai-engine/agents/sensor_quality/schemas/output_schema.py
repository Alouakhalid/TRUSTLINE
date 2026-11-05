"""Output schemas for Sensor Quality Agent reports."""
from typing import List, Dict, Optional, Any
from pydantic import BaseModel, Field
from .signal_schema import QualityStatus, IssueSeverity, TimeInterval

class IssueEvidence(BaseModel):
    metric_name: str = Field(..., description="Name of the quantified indicator")
    measured_value: float = Field(..., description="Observed numerical value")
    threshold_value: float = Field(..., description="Decision boundary threshold")
    units: Optional[str] = Field(default=None, description="Physical or normalized unit")
    confidence: Optional[float] = Field(default=1.0, ge=0.0, le=1.0, description="Certainty score")
    additional_context: Optional[Dict[str, Any]] = Field(default_factory=dict)

class DetectedIssue(BaseModel):
    reason_code: str = Field(..., description="Standardized diagnostic reason code")
    sensor: str = Field(..., description="Associated sensor identifier")
    severity: IssueSeverity = Field(..., description="Technical severity assessment")
    time_interval: Optional[TimeInterval] = Field(default=None, description="Temporal window of occurrence")
    evidence: List[IssueEvidence] = Field(default_factory=list, description="Empirical evidence supporting the issue")
    method: str = Field(..., description="Algorithmic or DSP detection technique")
    explanation: str = Field(..., description="Deterministic factual explanation")
    recommended_handling: Optional[str] = Field(default=None, description="Recommended downstream handling")

class SensorQualityMetrics(BaseModel):
    valid_sample_ratio: float = Field(..., ge=0.0, le=1.0)
    missing_sample_ratio: float = Field(..., ge=0.0, le=1.0)
    artifact_ratio: float = Field(..., ge=0.0, le=1.0)
    flatline_ratio: float = Field(..., ge=0.0, le=1.0)
    noise_index: float = Field(..., ge=0.0, le=1.0)
    timestamp_integrity: float = Field(..., ge=0.0, le=1.0)
    saturation_ratio: float = Field(default=0.0, ge=0.0, le=1.0)
    continuity_score: float = Field(default=1.0, ge=0.0, le=1.0)

class SensorQualityResult(BaseModel):
    sensor: str = Field(..., description="Sensor identifier")
    quality_score: float = Field(..., ge=0.0, le=1.0, description="Overall calibrated quality score")
    status: QualityStatus = Field(..., description="Deterministic status category")
    metrics: SensorQualityMetrics
    issues: List[DetectedIssue] = Field(default_factory=list)
    recommendation: str = Field(..., description="Actionable recommendation e.g. ACCEPT, REJECT")
    critical_failure: bool = Field(default=False, description="Flag indicating fatal sensor failure")
    sampling_rate: float = Field(..., gt=0.0)
    total_samples_analyzed: int = Field(..., ge=0)
    duration_seconds: float = Field(..., ge=0.0)

class OverallQuality(BaseModel):
    score: float = Field(..., ge=0.0, le=1.0, description="Aggregate recording quality score")
    status: QualityStatus = Field(..., description="Overall mission readiness status")
    valid_sensors_count: int = Field(..., ge=0)
    total_sensors_count: int = Field(..., ge=0)
    degraded_sensors: List[str] = Field(default_factory=list)
    rejected_sensors: List[str] = Field(default_factory=list)

class ProcessingDecision(BaseModel):
    can_proceed: bool = Field(..., description="Whether downstream agents may ingest data")
    warnings: List[str] = Field(default_factory=list)
    rejected_sensors: List[str] = Field(default_factory=list)
    next_agent: Optional[str] = Field(default="personal_health_agent")

class SensorQualityReport(BaseModel):
    agent: str = Field(default="sensor_quality_agent")
    report_version: str = Field(default="1.0")
    astronaut_id: str
    session_id: str
    recording_id: Optional[str] = None
    execution_timestamp: str
    overall_quality: OverallQuality
    sensors: Dict[str, SensorQualityResult]
    processing_decision: ProcessingDecision
    visualizations: List[str] = Field(default_factory=list)
    llm_explanation: Optional[Dict[str, Any]] = None
