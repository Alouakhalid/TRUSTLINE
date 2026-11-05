"""Deterministic artifact, clipping, and outlier spike detection."""
from typing import List, Tuple
import numpy as np
from ..schemas.signal_schema import SensorStreamData, IssueSeverity
from ..schemas.output_schema import DetectedIssue
from ..explainability.reason_codes import ReasonCode
from ..explainability.evidence_extractor import EvidenceExtractor

class ArtifactDetector:
    """Identifies transient artifacts, saturation, and mechanical clipping."""

    def __init__(self, spike_zscore_threshold: float = 4.5, clipping_ratio_threshold: float = 0.01):
        self.spike_zscore_threshold = spike_zscore_threshold
        self.clipping_ratio_threshold = clipping_ratio_threshold

    def detect_artifacts(self, stream: SensorStreamData) -> Tuple[float, float, List[DetectedIssue]]:
        issues: List[DetectedIssue] = []
        data = np.asarray(stream.data)

        if len(data) == 0:
            return 1.0, 1.0, issues

        if data.ndim > 1:
            signal_1d = data[:, 0]
        else:
            signal_1d = data

        clean_mask = ~(np.isnan(signal_1d) | np.isinf(signal_1d))
        if np.sum(clean_mask) == 0:
            return 1.0, 1.0, issues

        valid_data = signal_1d[clean_mask]
        total_valid = len(valid_data)

        min_val = float(np.min(valid_data))
        max_val = float(np.max(valid_data))
        span = max_val - min_val

        clipped_count = 0
        if span > 1e-6:
            at_min = np.isclose(valid_data, min_val, rtol=1e-5, atol=1e-8)
            at_max = np.isclose(valid_data, max_val, rtol=1e-5, atol=1e-8)
            clipped_count = int(np.sum(at_min) + np.sum(at_max))

        saturation_ratio = float(clipped_count) / float(total_valid)
        if saturation_ratio > self.clipping_ratio_threshold:
            evidence = EvidenceExtractor.build_evidence(
                metric_name="saturation_ratio",
                measured_value=saturation_ratio,
                threshold_value=self.clipping_ratio_threshold,
                units="ratio",
                confidence=0.95,
                context={"clamped_samples": clipped_count, "signal_min": min_val, "signal_max": max_val}
            )
            issues.append(DetectedIssue(
                reason_code=ReasonCode.SIGNAL_CLIPPING.value,
                sensor=stream.sensor,
                severity=IssueSeverity.HIGH if saturation_ratio > 0.05 else IssueSeverity.MODERATE,
                evidence=[evidence],
                method="Dynamic rail boundary clamping detection",
                explanation=f"Signal exhibits amplifier saturation or ADC clipping ({saturation_ratio:.2%} samples at boundaries).",
                recommended_handling="Adjust analog front-end gain or check sensor contact pressure."
            ))

        median_val = float(np.median(valid_data))
        mad = float(np.median(np.abs(valid_data - median_val)))
        spike_count = 0

        if mad > 1e-6:
            modified_zscores = 0.6745 * np.abs(valid_data - median_val) / mad
            spike_mask = modified_zscores > self.spike_zscore_threshold
            spike_count = int(np.sum(spike_mask))

        spike_ratio = float(spike_count) / float(total_valid)
        if spike_ratio > 0.005:
            evidence = EvidenceExtractor.build_evidence(
                metric_name="spike_ratio",
                measured_value=spike_ratio,
                threshold_value=0.005,
                units="ratio",
                confidence=0.90,
                context={"spike_count": spike_count, "z_threshold": self.spike_zscore_threshold}
            )
            issues.append(DetectedIssue(
                reason_code=ReasonCode.SIGNAL_SPIKES.value,
                sensor=stream.sensor,
                severity=IssueSeverity.MODERATE,
                evidence=[evidence],
                method="Median Absolute Deviation (MAD) modified Z-score",
                explanation=f"High-amplitude impulsive spikes detected ({spike_count} samples, {spike_ratio:.2%}).",
                recommended_handling="Apply median filter or segment around spike intervals."
            ))

        artifact_ratio = min(1.0, saturation_ratio + spike_ratio)
        return artifact_ratio, saturation_ratio, issues
