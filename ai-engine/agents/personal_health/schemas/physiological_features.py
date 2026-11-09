from enum import Enum
from typing import Dict, List, Optional, Any
from pydantic import BaseModel, Field

class MeasurementStatus(str, Enum):
    """Scientific validity and availability status of a physiological measurement."""
    AVAILABLE = "available"
    UNAVAILABLE = "unavailable"
    INVALID = "invalid"
    INSUFFICIENT_DATA = "insufficient_data"
    NOT_COMPUTED = "not_computed"
    INSUFFICIENT_VARIANCE = "insufficient_variance"

class HRVStatus(str, Enum):
    """Explicit scientific status of heart rate variability processing."""
    VALID = "VALID"
    INSUFFICIENT_R_PEAKS = "INSUFFICIENT_R_PEAKS"
    INSUFFICIENT_RR_INTERVALS = "INSUFFICIENT_RR_INTERVALS"
    INVALID_ECG_SIGNAL = "INVALID_ECG_SIGNAL"
    DETECTION_FAILURE = "DETECTION_FAILURE"
    ZERO_VARIABILITY = "ZERO_VARIABILITY"
    INVALID_INTERVALS = "INVALID_INTERVALS"

class HRVDiagnosticReport(BaseModel):
    """Detailed audit metrics and quality provenance for heart rate variability."""
    ecg_sampling_rate: float
    ecg_duration_seconds: float
    total_r_peaks_detected: int
    valid_r_peaks: int
    total_rr_intervals: int
    valid_nn_intervals: int
    invalid_interval_count: int
    mean_rr_ms: Optional[float] = None
    median_rr_ms: Optional[float] = None
    sdnn_ms: Optional[float] = None
    rmssd_ms: Optional[float] = None
    hrv_status: HRVStatus = Field(default=HRVStatus.VALID)
    detection_algorithm: str = "SciPy find_peaks (Pan-Tompkins heuristic)"
    processing_warnings: List[str] = Field(default_factory=list)
    calculation_validity: bool = True

    @property
    def r_peaks_detected(self) -> int:
        """Alias for total_r_peaks_detected."""
        return self.total_r_peaks_detected

    @property
    def valid_rr_intervals_count(self) -> int:
        """Alias for valid_nn_intervals."""
        return self.valid_nn_intervals

    @property
    def artifact_count(self) -> int:
        """Alias for invalid_interval_count."""
        return self.invalid_interval_count

    @property
    def diagnostic_note(self) -> str:
        """Summary diagnostic narrative from warnings or nominal state."""
        if self.processing_warnings:
            return " ".join(self.processing_warnings)
        return "Normal physiological beat-to-beat variability verified."

class ExtractedFeature(BaseModel):
    """Individual extracted feature with full provenance and validity metadata."""
    feature_name: str
    value: float
    unit: str
    sensor_source: str
    time_window_seconds: float
    extraction_method: str
    quality_status: str
    validity_status: str
    measurement_status: MeasurementStatus = Field(default=MeasurementStatus.AVAILABLE)
    status_reason: Optional[str] = Field(default=None)
    exploratory_ultra_short_term: bool = Field(default=False)

class Core14Features(BaseModel):
    """The 14 core physiological features required by production ML artifacts."""
    hr_mean_bpm: float = Field(..., description="Mean heart rate in beats per minute")
    hr_std_bpm: float = Field(..., description="Standard deviation of heart rate")
    hrv_rmssd_ms: float = Field(..., description="Root mean square of successive RR interval differences")
    hrv_sdnn_ms: float = Field(..., description="Standard deviation of NN intervals")
    eda_mean: float = Field(..., description="Mean skin conductance in microsiemens")
    eda_std: float = Field(..., description="Standard deviation of skin conductance")
    eda_iqr: float = Field(..., description="Interquartile range of skin conductance")
    resp_rate_bpm: float = Field(..., description="Breathing rate in breaths per minute")
    resp_std: float = Field(..., description="Respiration signal amplitude variability")
    temp_mean: float = Field(..., description="Mean skin temperature in degrees Celsius")
    temp_std: float = Field(..., description="Standard deviation of skin temperature")
    emg_rms: float = Field(..., description="Root mean square of surface electromyogram")
    acc_magnitude_mean: float = Field(..., description="Mean tri-axial acceleration magnitude in g")
    acc_magnitude_std: float = Field(..., description="Standard deviation of tri-axial acceleration magnitude")

    def to_feature_dict(self) -> Dict[str, float]:
        """Convert features to dictionary in exact required key ordering."""
        return {
            "hr_mean_bpm": self.hr_mean_bpm,
            "hr_std_bpm": self.hr_std_bpm,
            "hrv_rmssd_ms": self.hrv_rmssd_ms,
            "hrv_sdnn_ms": self.hrv_sdnn_ms,
            "eda_mean": self.eda_mean,
            "eda_std": self.eda_std,
            "eda_iqr": self.eda_iqr,
            "resp_rate_bpm": self.resp_rate_bpm,
            "resp_std": self.resp_std,
            "temp_mean": self.temp_mean,
            "temp_std": self.temp_std,
            "emg_rms": self.emg_rms,
            "acc_magnitude_mean": self.acc_magnitude_mean,
            "acc_magnitude_std": self.acc_magnitude_std
        }

class PhysiologicalFeatureReport(BaseModel):
    """Aggregated feature extraction report across all physiological channels."""
    astronaut_id: str
    session_id: str
    window_duration_seconds: float
    core_features: Optional[Core14Features] = None
    all_features: List[ExtractedFeature] = Field(default_factory=list)
    extraction_warnings: List[str] = Field(default_factory=list)
    hrv_diagnostics: Optional[HRVDiagnosticReport] = None
    has_valid_core14: bool = Field(default=False)
