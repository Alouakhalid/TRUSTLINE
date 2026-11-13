"""Schemas and data models for astronaut personal health baseline and deviation analysis."""
from datetime import datetime
from enum import Enum
from typing import Dict, List, Optional, Any
from pydantic import BaseModel, Field

class BaselineReadinessState(str, Enum):
    """Lifecycle readiness state of an astronaut's personal physiological baseline."""
    INSUFFICIENT_DATA = "INSUFFICIENT_DATA"
    PROVISIONAL = "PROVISIONAL"
    ESTABLISHED = "ESTABLISHED"
    STALE = "STALE"
    SUSPENDED = "SUSPENDED"
    INVALID = "INVALID"

class BaselineContextType(str, Enum):
    """Physiological and operational context during observation."""
    REST = "REST"
    ACTIVITY = "ACTIVITY"
    NOMINAL_OPERATIONAL = "NOMINAL_OPERATIONAL"
    UNKNOWN = "UNKNOWN"

class DeviationDirection(str, Enum):
    """Direction of physiological deviation relative to personal reference."""
    NOMINAL = "NOMINAL"
    ELEVATED = "ELEVATED"
    DEPRESSED = "DEPRESSED"
    INDETERMINATE = "INDETERMINATE"

class DeviationSeverity(str, Enum):
    """Statistical magnitude tier of physiological deviation."""
    NOMINAL = "NOMINAL"          # |z| < 2.0
    MILD = "MILD"                # 2.0 <= |z| < 3.0
    MODERATE = "MODERATE"        # 3.0 <= |z| < 4.5
    SIGNIFICANT = "SIGNIFICANT"  # 4.5 <= |z| < 6.0
    EXTREME = "EXTREME"          # |z| >= 6.0

class UpdateRejectionReason(str, Enum):
    """Explicit safety reason preventing baseline updating."""
    ANOMALOUS_OBSERVATION = "ANOMALOUS_OBSERVATION"
    POOR_SENSOR_QUALITY = "POOR_SENSOR_QUALITY"
    CROSS_ASTRONAUT_VIOLATION = "CROSS_ASTRONAUT_VIOLATION"
    UNKNOWN_IDENTITY = "UNKNOWN_IDENTITY"
    INVALID_TIMESTAMP = "INVALID_TIMESTAMP"
    DUPLICATE_SESSION = "DUPLICATE_SESSION"
    INSUFFICIENT_DURATION = "INSUFFICIENT_DURATION"
    CORRUPTED_FEATURES = "CORRUPTED_FEATURES"

class FeatureBaselineStats(BaseModel):
    """Robust statistical reference metrics for an individual physiological feature."""
    feature_name: str
    unit: str
    median: float
    mad: float
    iqr: float
    mean: float
    std: float
    min_val: float
    max_val: float
    p10: float
    p25: float
    p75: float
    p90: float
    sample_count: int
    count: Optional[int] = None
    q25: Optional[float] = None
    q75: Optional[float] = None
    noise_floor: float = Field(default=0.01)

    def model_post_init(self, __context: Any) -> None:
        if self.count is None:
            self.count = self.sample_count
        if self.q25 is None:
            self.q25 = self.p25
        if self.q75 is None:
            self.q75 = self.p75

class ContextualBaselineProfile(BaseModel):
    """Feature statistics partition for a specific operational or physiological context."""
    context_type: BaselineContextType
    sample_count: int = Field(default=0)
    features: Dict[str, FeatureBaselineStats] = Field(default_factory=dict)

class PersonalBaselineProfile(BaseModel):
    """Complete versioned physiological baseline profile for an individual astronaut."""
    astronaut_id: str
    baseline_version: int = Field(default=1)
    readiness_state: BaselineReadinessState = Field(default=BaselineReadinessState.INSUFFICIENT_DATA)
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)
    last_observation_timestamp: Optional[datetime] = None
    total_calibrated_sessions: int = Field(default=0)
    total_valid_observations: int = Field(default=0)
    observation_period_days: float = Field(default=0.0)
    general_profile: ContextualBaselineProfile = Field(default_factory=lambda: ContextualBaselineProfile(context_type=BaselineContextType.NOMINAL_OPERATIONAL))
    context_profiles: Dict[Any, ContextualBaselineProfile] = Field(default_factory=dict)
    provenance_notes: str = Field(default="Longitudinal individualized physiological baseline.")

    def get_context_profile(self, context: Any) -> ContextualBaselineProfile:
        """Retrieve contextual profile or fall back to general profile."""
        if context is not None:
            if context in self.context_profiles:
                return self.context_profiles[context]
            key_val = getattr(context, "value", str(context))
            if key_val in self.context_profiles:
                return self.context_profiles[key_val]
        return self.general_profile

class FeatureDeviationResult(BaseModel):
    """Single feature deviation evaluation relative to personal baseline."""
    feature_name: str
    observed_value: float
    unit: str
    reference_median: float
    reference_mad: float
    robust_z_score: float
    quantile_rank: Optional[float] = None
    deviation_direction: DeviationDirection
    deviation_severity: DeviationSeverity
    context_used: BaselineContextType
    is_statistically_unusual: bool
    explanation: str

class PersonalDeviationReport(BaseModel):
    """Comprehensive evaluation of current observation session against personal baseline."""
    astronaut_id: str
    session_id: str
    timestamp: datetime = Field(default_factory=datetime.utcnow)
    baseline_version: int = Field(default=0)
    readiness_state: BaselineReadinessState
    context_detected: BaselineContextType
    context_fallback_applied: bool = Field(default=False)
    context_fallback_reason: Optional[str] = None
    feature_deviations: Dict[str, FeatureDeviationResult] = Field(default_factory=dict)
    composite_deviation_score: float = Field(default=0.0)
    persistent_deviation_detected: bool = Field(default=False)
    unusual_signals_count: int = Field(default=0)
    abstention_reason: Optional[str] = None
    provenance: str

    @property
    def is_statistically_significant(self) -> bool:
        return self.unusual_signals_count > 0 or self.composite_deviation_score >= 2.0

    @property
    def clinically_concerning(self) -> bool:
        return self.composite_deviation_score >= 3.0 or any(
            d.deviation_severity in (DeviationSeverity.SIGNIFICANT, DeviationSeverity.EXTREME)
            for d in self.feature_deviations.values()
        )

class ObservationSession(BaseModel):
    """Raw physiological observation session payload ready for eligibility audit."""
    session_id: str
    astronaut_id: str
    timestamp: datetime = Field(default_factory=datetime.utcnow)
    duration_seconds: float = Field(default=300.0)
    context_type: BaselineContextType = Field(default=BaselineContextType.NOMINAL_OPERATIONAL)
    context: Optional[BaselineContextType] = None
    sqa_overall_score: Optional[float] = None
    features: Dict[str, float] = Field(default_factory=dict)
    sensor_quality_scores: Dict[str, float] = Field(default_factory=dict)
    is_valid: bool = Field(default=True)
    rejection_reason: Optional[str] = None

class BaselineUpdateLog(BaseModel):
    """Audit log entry capturing a baseline snapshot change or rejected update."""
    log_id: str
    astronaut_id: str
    from_version: int
    to_version: int
    source_session_id: str
    update_timestamp: datetime = Field(default_factory=datetime.utcnow)
    update_reason: str
    is_successful: bool
    rejection_reason: Optional[UpdateRejectionReason] = None
