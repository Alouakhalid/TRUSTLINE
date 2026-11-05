"""Hierarchical quality scoring engine with critical failure protection."""
from typing import Dict, List, Optional
from ..schemas.signal_schema import QualityStatus, IssueSeverity
from ..schemas.output_schema import (
    SensorQualityMetrics,
    SensorQualityResult,
    OverallQuality,
    DetectedIssue
)
from ..config.settings import get_settings

class QualityScorer:
    """Calculates component, sensor, and session quality scores."""

    def __init__(self, weights: Optional[Dict[str, float]] = None):
        cfg = get_settings()
        self.weights = weights or cfg.component_weights

    def score_sensor(
        self,
        sensor: str,
        metrics: SensorQualityMetrics,
        issues: List[DetectedIssue],
        sampling_rate: float,
        total_samples: int,
        duration_seconds: float
    ) -> SensorQualityResult:
        w_valid = self.weights.get("valid_sample_ratio", 0.30)
        w_ts = self.weights.get("timestamp_integrity", 0.25)
        w_art = self.weights.get("artifact_free_ratio", 0.20)
        w_noise = self.weights.get("noise_score", 0.15)
        w_cont = self.weights.get("continuity_score", 0.10)

        artifact_free = max(0.0, 1.0 - metrics.artifact_ratio)
        noise_free = max(0.0, 1.0 - metrics.noise_index)

        raw_score = (
            w_valid * metrics.valid_sample_ratio +
            w_ts * metrics.timestamp_integrity +
            w_art * artifact_free +
            w_noise * noise_free +
            w_cont * metrics.continuity_score
        )

        has_critical_issue = any(issue.severity == IssueSeverity.CRITICAL for issue in issues)
        fatal_flatline = metrics.flatline_ratio >= 0.30
        fatal_missing = metrics.missing_sample_ratio >= 0.20
        fatal_timestamp = metrics.timestamp_integrity <= 0.30

        critical_failure = has_critical_issue or fatal_flatline or fatal_missing or fatal_timestamp

        if critical_failure:
            final_score = min(raw_score, 0.40)
            status = QualityStatus.INVALID
            recommendation = "REJECT"
        elif total_samples == 0:
            final_score = 0.0
            status = QualityStatus.INSUFFICIENT_DATA
            recommendation = "REJECT"
        elif raw_score >= 0.90:
            final_score = raw_score
            status = QualityStatus.VALID
            recommendation = "ACCEPT"
        elif raw_score >= 0.75:
            final_score = raw_score
            status = QualityStatus.ACCEPTABLE_WITH_WARNING
            recommendation = "ACCEPT_WITH_WARNING"
        elif raw_score >= 0.50:
            final_score = raw_score
            status = QualityStatus.DEGRADED
            recommendation = "FLAG_DEGRADED"
        else:
            final_score = raw_score
            status = QualityStatus.INVALID
            recommendation = "REJECT"

        return SensorQualityResult(
            sensor=sensor,
            quality_score=round(float(final_score), 4),
            status=status,
            metrics=metrics,
            issues=issues,
            recommendation=recommendation,
            critical_failure=critical_failure,
            sampling_rate=float(sampling_rate),
            total_samples_analyzed=int(total_samples),
            duration_seconds=round(float(duration_seconds), 2)
        )

    def score_overall_session(self, sensor_results: Dict[str, SensorQualityResult]) -> OverallQuality:
        if not sensor_results:
            return OverallQuality(
                score=0.0,
                status=QualityStatus.INSUFFICIENT_DATA,
                valid_sensors_count=0,
                total_sensors_count=0,
                degraded_sensors=[],
                rejected_sensors=[]
            )

        total_sensors = len(sensor_results)
        scores = [res.quality_score for res in sensor_results.values()]
        mean_score = sum(scores) / float(total_sensors)

        degraded = [s for s, res in sensor_results.items() if res.status == QualityStatus.DEGRADED]
        rejected = [s for s, res in sensor_results.items() if res.status == QualityStatus.INVALID]
        valid_count = sum(1 for res in sensor_results.values() if res.status in {QualityStatus.VALID, QualityStatus.ACCEPTABLE_WITH_WARNING})

        if len(rejected) >= total_sensors / 2.0 or mean_score < 0.50:
            overall_status = QualityStatus.INVALID
        elif rejected or degraded or mean_score < 0.85:
            overall_status = QualityStatus.ACCEPTABLE_WITH_WARNING if valid_count >= total_sensors / 2 else QualityStatus.DEGRADED
        else:
            overall_status = QualityStatus.VALID

        return OverallQuality(
            score=round(float(mean_score), 4),
            status=overall_status,
            valid_sensors_count=valid_count,
            total_sensors_count=total_sensors,
            degraded_sensors=degraded,
            rejected_sensors=rejected
        )
