"""Schemas for ML model registry and inference predictions."""
from datetime import datetime
from typing import Dict, List, Optional, Any
from pydantic import BaseModel, Field

class ModelMetadata(BaseModel):
    """Metadata describing a registered ML model artifact."""
    model_id: str
    model_name: str
    version: str
    model_type: str
    target_definition: str
    decision_threshold: float
    expected_features: List[str]
    training_dataset: str
    known_limitations: str
    is_active: bool = True

class MLInferenceResult(BaseModel):
    """Calibrated inference prediction output from production ML model."""
    model_id: str
    model_name: str
    version: str
    target_definition: str
    stress_probability: float = Field(..., ge=0.0, le=1.0)
    verdict: str = Field(..., description="NORMAL or STRESS_ALERT")
    threshold_applied: float = Field(default=0.50)
    raw_feature_values: Dict[str, float] = Field(default_factory=dict)
    inference_timestamp: datetime = Field(default_factory=datetime.utcnow)
    validity_status: str = Field(default="VALID")
    clinical_disclaimer: str = Field(
        default="Empirical acute stress probability derived from WESAD physiological telemetry benchmark. Not an approved medical diagnosis of clinical anxiety or organic cardiovascular pathology."
    )
