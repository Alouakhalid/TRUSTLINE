"""Temporal integrity and sampling interval consistency checks."""
from typing import List, Tuple
import numpy as np
from ..schemas.signal_schema import SensorStreamData, IssueSeverity, TimeInterval
from ..schemas.output_schema import DetectedIssue
from ..explainability.reason_codes import ReasonCode
from ..explainability.evidence_extractor import EvidenceExtractor

class TemporalChecker:
    """Verifies sampling rate stability, monotonic time flow, and gap absence."""

    def __init__(self, max_jitter_ratio: float = 0.10, gap_threshold_multiplier: float = 2.5):
        self.max_jitter_ratio = max_jitter_ratio
        self.gap_threshold_multiplier = gap_threshold_multiplier

    def check_temporal_integrity(self, stream: SensorStreamData) -> Tuple[float, float, List[DetectedIssue]]:
        issues: List[DetectedIssue] = []
        timestamps = np.asarray(stream.timestamps)
        total = len(timestamps)

        if total < 2:
            return 1.0, 1.0, issues

        diffs = np.diff(timestamps)
        nominal_dt = 1.0 / stream.sampling_rate if stream.sampling_rate > 0 else 0.0

        negative_indices = np.where(diffs < 0.0)[0]
        if len(negative_indices) > 0:
            evidence = EvidenceExtractor.build_evidence(
                metric_name="backwards_timestamp_count",
                measured_value=float(len(negative_indices)),
                threshold_value=0.0,
                units="count",
                confidence=1.0,
                context={"first_backward_index": int(negative_indices[0])}
            )
            issues.append(DetectedIssue(
                reason_code=ReasonCode.TIMESTAMP_INCONSISTENCY.value,
                sensor=stream.sensor,
                severity=IssueSeverity.CRITICAL,
                time_interval=TimeInterval(
                    start=float(timestamps[negative_indices[0]]),
                    end=float(timestamps[min(negative_indices[0] + 1, total - 1)])
                ),
                evidence=[evidence],
                method="Monotonic difference inspection",
                explanation="Non-monotonic timestamps detected; time flows backwards or packets arrived out of order.",
                recommended_handling="Reorder packets by acquisition hardware sequence counter."
            ))

        duplicate_indices = np.where(diffs == 0.0)[0]
        if len(duplicate_indices) > 0:
            dup_ratio = float(len(duplicate_indices)) / float(total)
            evidence = EvidenceExtractor.build_evidence(
                metric_name="duplicate_timestamp_ratio",
                measured_value=dup_ratio,
                threshold_value=0.0,
                units="ratio",
                confidence=1.0
            )
            issues.append(DetectedIssue(
                reason_code=ReasonCode.TIMESTAMP_DUPLICATES.value,
                sensor=stream.sensor,
                severity=IssueSeverity.HIGH if dup_ratio > 0.01 else IssueSeverity.MODERATE,
                evidence=[evidence],
                method="Zero-difference delta t analysis",
                explanation=f"Identified {len(duplicate_indices)} duplicate timestamps ({dup_ratio:.4f} ratio).",
                recommended_handling="Deduplicate acquisition records based on hardware counter."
            ))

        gap_threshold = nominal_dt * self.gap_threshold_multiplier
        gap_indices = np.where(diffs > gap_threshold)[0]
        continuity_score = 1.0

        if len(gap_indices) > 0:
            total_gap_duration = float(np.sum(diffs[gap_indices] - nominal_dt))
            continuity_score = max(0.0, 1.0 - (total_gap_duration / max(1.0, stream.duration_seconds)))
            first_gap_idx = gap_indices[0]
            evidence = EvidenceExtractor.build_evidence(
                metric_name="max_gap_duration_sec",
                measured_value=float(np.max(diffs[gap_indices])),
                threshold_value=float(gap_threshold),
                units="seconds",
                confidence=1.0,
                context={"gap_count": len(gap_indices), "total_gap_seconds": total_gap_duration}
            )
            issues.append(DetectedIssue(
                reason_code=ReasonCode.TIMESTAMP_GAP_DETECTED.value,
                sensor=stream.sensor,
                severity=IssueSeverity.HIGH if total_gap_duration > 5.0 else IssueSeverity.MODERATE,
                time_interval=TimeInterval(
                    start=float(timestamps[first_gap_idx]),
                    end=float(timestamps[first_gap_idx + 1])
                ),
                evidence=[evidence],
                method="Sampling interval gap thresholding",
                explanation=f"Detected {len(gap_indices)} transmission or acquisition gaps totaling {total_gap_duration:.2f}s.",
                recommended_handling="Log data dropout and verify wireless link margin."
            ))

        positive_diffs = diffs[diffs > 0.0]
        if len(positive_diffs) > 0:
            observed_mean_dt = float(np.mean(positive_diffs))
            observed_std_dt = float(np.std(positive_diffs))
            jitter_ratio = observed_std_dt / observed_mean_dt if observed_mean_dt > 0 else 0.0
            timestamp_integrity = max(0.0, 1.0 - min(1.0, jitter_ratio / self.max_jitter_ratio))

            if jitter_ratio > self.max_jitter_ratio:
                evidence = EvidenceExtractor.build_evidence(
                    metric_name="timestamp_jitter_ratio",
                    measured_value=jitter_ratio,
                    threshold_value=self.max_jitter_ratio,
                    units="ratio",
                    confidence=1.0,
                    context={"observed_mean_dt": observed_mean_dt, "nominal_dt": nominal_dt}
                )
                issues.append(DetectedIssue(
                    reason_code=ReasonCode.TIMESTAMP_JITTER_HIGH.value,
                    sensor=stream.sensor,
                    severity=IssueSeverity.MODERATE,
                    evidence=[evidence],
                    method="Delta t variance analysis",
                    explanation=f"Sampling jitter ratio ({jitter_ratio:.4f}) exceeded nominal limit ({self.max_jitter_ratio:.4f}).",
                    recommended_handling="Resample via timestamp-aware spline if downstream algorithm requires uniform grid."
                ))
        else:
            timestamp_integrity = 0.0

        if len(negative_indices) > 0:
            timestamp_integrity = min(timestamp_integrity, 0.20)

        return timestamp_integrity, continuity_score, issues
