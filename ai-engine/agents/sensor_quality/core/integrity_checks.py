"""Signal integrity checks module."""
from typing import List, Tuple
import numpy as np
from ..schemas.signal_schema import SensorStreamData, IssueSeverity
from ..schemas.output_schema import DetectedIssue
from ..explainability.reason_codes import ReasonCode
from ..explainability.evidence_extractor import EvidenceExtractor

class IntegrityChecker:
    """Evaluates raw signal completeness, representation types, and missing values."""

    def __init__(self, max_acceptable_nan_ratio: float = 0.05, critical_nan_ratio: float = 0.20):
        self.max_acceptable_nan_ratio = max_acceptable_nan_ratio
        self.critical_nan_ratio = critical_nan_ratio

    def check_integrity(self, stream: SensorStreamData) -> Tuple[float, float, List[DetectedIssue]]:
        issues: List[DetectedIssue] = []
        total_samples = stream.total_samples

        if total_samples == 0 or stream.data is None or len(stream.data) == 0:
            evidence = EvidenceExtractor.build_evidence(
                metric_name="total_samples",
                measured_value=0.0,
                threshold_value=1.0,
                units="count",
                confidence=1.0
            )
            issues.append(DetectedIssue(
                reason_code=ReasonCode.SIGNAL_EMPTY.value,
                sensor=stream.sensor,
                severity=IssueSeverity.CRITICAL,
                evidence=[evidence],
                method="Array shape evaluation",
                explanation="The received signal contains zero samples.",
                recommended_handling="Reject stream and check sensor acquisition interface."
            ))
            return 0.0, 1.0, issues

        if not np.issubdtype(stream.data.dtype, np.number):
            evidence = EvidenceExtractor.build_evidence(
                metric_name="numeric_dtype",
                measured_value=0.0,
                threshold_value=1.0,
                units="boolean",
                confidence=1.0
            )
            issues.append(DetectedIssue(
                reason_code=ReasonCode.SIGNAL_TYPE_ERROR.value,
                sensor=stream.sensor,
                severity=IssueSeverity.CRITICAL,
                evidence=[evidence],
                method="Type inspection",
                explanation=f"Signal data has non-numeric dtype: {stream.data.dtype}",
                recommended_handling="Reject stream and verify digitization format."
            ))
            return 0.0, 1.0, issues

        data_arr = np.asarray(stream.data)
        nan_mask = np.isnan(data_arr) | np.isinf(data_arr)
        nan_count = int(np.sum(nan_mask))
        nan_ratio = float(nan_count) / float(total_samples * (data_arr.shape[1] if data_arr.ndim > 1 else 1))
        valid_ratio = 1.0 - nan_ratio

        if nan_ratio > self.max_acceptable_nan_ratio:
            severity = IssueSeverity.CRITICAL if nan_ratio >= self.critical_nan_ratio else IssueSeverity.HIGH
            evidence = EvidenceExtractor.build_evidence(
                metric_name="missing_sample_ratio",
                measured_value=nan_ratio,
                threshold_value=self.max_acceptable_nan_ratio,
                units="ratio",
                confidence=1.0,
                context={"missing_count": nan_count, "total_samples": total_samples}
            )
            issues.append(DetectedIssue(
                reason_code=ReasonCode.SIGNAL_MISSING_VALUES.value,
                sensor=stream.sensor,
                severity=severity,
                evidence=[evidence],
                method="NaN and Inf mask analysis",
                explanation=f"Missing or infinite samples ratio ({nan_ratio:.4f}) exceeded technical tolerance ({self.max_acceptable_nan_ratio:.4f}).",
                recommended_handling="Discard missing intervals or reject stream if mission critical."
            ))

        return valid_ratio, nan_ratio, issues
