"""Flatline, stuck sensor, and zero-variance detection."""
from typing import List, Tuple
import numpy as np
from ..schemas.signal_schema import SensorStreamData, IssueSeverity, TimeInterval
from ..schemas.output_schema import DetectedIssue
from ..explainability.reason_codes import ReasonCode
from ..explainability.evidence_extractor import EvidenceExtractor

class FlatlineDetector:
    """Detects constant-value segments and disconnected sensor leads."""

    def __init__(self, variance_threshold: float = 1e-6, min_duration_seconds: float = 3.0):
        self.variance_threshold = variance_threshold
        self.min_duration_seconds = min_duration_seconds

    def detect_flatline(self, stream: SensorStreamData) -> Tuple[float, List[DetectedIssue]]:
        issues: List[DetectedIssue] = []
        fs = stream.sampling_rate
        data = np.asarray(stream.data)

        if len(data) == 0 or fs <= 0:
            return 0.0, issues

        if data.ndim > 1:
            signal_1d = data[:, 0]
        else:
            signal_1d = data

        clean_mask = ~(np.isnan(signal_1d) | np.isinf(signal_1d))
        valid_indices = np.where(clean_mask)[0]
        if len(valid_indices) == 0:
            return 1.0, issues

        valid_data = signal_1d[valid_indices]
        valid_ts = np.asarray(stream.timestamps)[valid_indices]

        window_samples = max(2, int(self.min_duration_seconds * fs))
        if len(valid_data) < window_samples:
            overall_var = float(np.var(valid_data))
            if overall_var < self.variance_threshold:
                evidence = EvidenceExtractor.build_evidence(
                    metric_name="signal_variance",
                    measured_value=overall_var,
                    threshold_value=self.variance_threshold,
                    units="variance",
                    confidence=1.0
                )
                issues.append(DetectedIssue(
                    reason_code=ReasonCode.SENSOR_FLATLINE.value,
                    sensor=stream.sensor,
                    severity=IssueSeverity.CRITICAL,
                    evidence=[evidence],
                    method="Global variance inspection",
                    explanation=f"Signal variance ({overall_var:.2e}) is near-zero over the entire recording.",
                    recommended_handling="Check lead attachment and sensor power."
                ))
                return 1.0, issues
            return 0.0, issues

        diffs = np.diff(valid_data)
        zero_diffs = np.isclose(diffs, 0.0, atol=1e-8)

        flat_samples = 0
        current_run = 0
        first_flat_start_idx = None

        for idx, is_zero in enumerate(zero_diffs):
            if is_zero:
                current_run += 1
                if current_run >= window_samples:
                    flat_samples += 1
                    if first_flat_start_idx is None:
                        first_flat_start_idx = idx - current_run + 1
            else:
                current_run = 0

        flatline_ratio = float(flat_samples) / float(len(valid_data))

        if flatline_ratio > 0.05:
            severity = IssueSeverity.CRITICAL if flatline_ratio > 0.30 else IssueSeverity.HIGH
            context_dict = {"flat_samples": flat_samples, "min_duration_sec": self.min_duration_seconds}
            evidence = EvidenceExtractor.build_evidence(
                metric_name="flatline_sample_ratio",
                measured_value=flatline_ratio,
                threshold_value=0.05,
                units="ratio",
                confidence=1.0,
                context=context_dict
            )

            time_interval = None
            if first_flat_start_idx is not None and first_flat_start_idx < len(valid_ts):
                t_start = float(valid_ts[first_flat_start_idx])
                t_end = float(valid_ts[min(first_flat_start_idx + window_samples, len(valid_ts) - 1)])
                time_interval = TimeInterval(start=t_start, end=t_end)

            issues.append(DetectedIssue(
                reason_code=ReasonCode.SENSOR_FLATLINE.value,
                sensor=stream.sensor,
                severity=severity,
                time_interval=time_interval,
                evidence=[evidence],
                method="Consecutive zero-derivative window analysis",
                explanation=f"Constant-value flatline segment detected covering {flatline_ratio:.2%} of signal duration.",
                recommended_handling="Flag as sensor detachment or hardware acquisition freeze."
            ))

        return flatline_ratio, issues
