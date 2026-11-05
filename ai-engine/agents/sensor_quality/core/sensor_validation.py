"""Sensor-specific technical operational range and transducer validation."""
from typing import List, Tuple, Dict
import numpy as np
from ..schemas.signal_schema import SensorStreamData, IssueSeverity
from ..schemas.output_schema import DetectedIssue
from ..explainability.reason_codes import ReasonCode
from ..explainability.evidence_extractor import EvidenceExtractor

class SensorValidator:
    """Validates technical operational plausibility per biosignal modality."""

    OPERATIONAL_LIMITS: Dict[str, Tuple[float, float]] = {
        "ECG": (-5.0, 5.0),
        "EDA": (0.01, 100.0),
        "RESP": (-25.0, 25.0),
        "EMG": (-10.0, 10.0),
        "ACC": (-16.0, 16.0),
        "TEMP": (15.0, 45.0)
    }

    def validate_sensor(self, stream: SensorStreamData) -> Tuple[bool, List[DetectedIssue]]:
        issues: List[DetectedIssue] = []
        sensor_key = stream.sensor.upper()
        limits = self.OPERATIONAL_LIMITS.get(sensor_key)

        if limits is None:
            return True, issues

        lower_limit, upper_limit = limits
        data = np.asarray(stream.data)

        if data.ndim > 1:
            signal_1d = data[:, 0]
        else:
            signal_1d = data

        clean_mask = ~(np.isnan(signal_1d) | np.isinf(signal_1d))
        if np.sum(clean_mask) == 0:
            return False, issues

        valid_vals = signal_1d[clean_mask]
        out_of_range_mask = (valid_vals < lower_limit) | (valid_vals > upper_limit)
        out_count = int(np.sum(out_of_range_mask))

        if out_count > 0:
            out_ratio = float(out_count) / float(len(valid_vals))
            if out_ratio > 0.01:
                severity = IssueSeverity.HIGH if out_ratio > 0.10 else IssueSeverity.MODERATE
                evidence = EvidenceExtractor.build_evidence(
                    metric_name="out_of_range_sample_ratio",
                    measured_value=out_ratio,
                    threshold_value=0.01,
                    units="ratio",
                    confidence=1.0,
                    context={"min_observed": float(np.min(valid_vals)), "max_observed": float(np.max(valid_vals))}
                )
                issues.append(DetectedIssue(
                    reason_code=ReasonCode.TEMP_OUT_OF_RANGE.value if sensor_key == "TEMP" else ReasonCode.SENSOR_SATURATION.value,
                    sensor=stream.sensor,
                    severity=severity,
                    evidence=[evidence],
                    method="Transducer technical boundary inspection",
                    explanation=f"Sensor values breached operational limits [{lower_limit}, {upper_limit}] {stream.unit} ({out_ratio:.2%} samples).",
                    recommended_handling="Calibrate analog transducer or verify sensor skin coupling."
                ))
                return False, issues

        return True, issues
