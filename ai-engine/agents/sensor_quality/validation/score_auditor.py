"""Independent mathematical audit and reproduction of sensor and session quality scores."""
from typing import Dict, List, Tuple
import numpy as np
try:
    from ..schemas.output_schema import SensorQualityResult, OverallQuality, SensorQualityMetrics
    from ..schemas.signal_schema import IssueSeverity
    from .schemas import ScoreAuditRecord, ValidationCheckResult, CheckStatus
except ImportError:
    try:
        from schemas.output_schema import SensorQualityResult, OverallQuality, SensorQualityMetrics
        from schemas.signal_schema import IssueSeverity
        from validation.schemas import ScoreAuditRecord, ValidationCheckResult, CheckStatus
    except ImportError:
        from sensor_quality.schemas.output_schema import SensorQualityResult, OverallQuality, SensorQualityMetrics
        from sensor_quality.schemas.signal_schema import IssueSeverity
        from sensor_quality.validation.schemas import ScoreAuditRecord, ValidationCheckResult, CheckStatus

class QualityScoreAuditor:
    """Verifies numerical formulas, component weighting, and aggregation reproduction."""

    COMPONENT_WEIGHTS = {
        "valid_sample_ratio": 0.30,
        "timestamp_integrity": 0.25,
        "artifact_free_ratio": 0.20,
        "noise_score": 0.15,
        "continuity_score": 0.10
    }

    def audit_scores(
        self,
        sensor_results: Dict[str, SensorQualityResult],
        overall: OverallQuality
    ) -> Tuple[List[ScoreAuditRecord], List[ValidationCheckResult]]:
        records: List[ScoreAuditRecord] = []
        checks: List[ValidationCheckResult] = []

        recalculated_scores = []
        for sensor_name, res in sensor_results.items():
            record, check = self.audit_sensor_score(sensor_name, res)
            records.append(record)
            checks.append(check)
            recalculated_scores.append(record.recalculated_score)

        if len(recalculated_scores) > 0:
            mean_recalculated = round(float(sum(recalculated_scores) / len(recalculated_scores)), 4)
            reported_overall = round(float(overall.score), 4)
            delta = abs(reported_overall - mean_recalculated)
            is_match = delta <= 0.0005

            record_overall = ScoreAuditRecord(
                sensor="OVERALL",
                reported_score=reported_overall,
                recalculated_score=mean_recalculated,
                delta=round(delta, 6),
                is_match=is_match,
                component_breakdown={
                    "sensor_count": float(len(recalculated_scores)),
                    "recalculated_mean": mean_recalculated
                }
            )
            records.append(record_overall)

            if is_match:
                checks.append(ValidationCheckResult(
                    check_id="SCORE-OVERALL-REPRODUCED",
                    category="QUALITY_SCORE",
                    target="OVERALL",
                    status=CheckStatus.PASSED,
                    message=f"Overall session score ({reported_overall:.4f}) matches arithmetic mean ({mean_recalculated:.4f}).",
                    evidence={"reported": reported_overall, "recalculated": mean_recalculated, "delta": delta}
                ))
            else:
                checks.append(ValidationCheckResult(
                    check_id="SCORE-OVERALL-MISMATCH",
                    category="QUALITY_SCORE",
                    target="OVERALL",
                    status=CheckStatus.FAILED,
                    message=f"Overall score ({reported_overall:.4f}) does not match mean of sensor scores ({mean_recalculated:.4f}).",
                    evidence={"reported": reported_overall, "recalculated": mean_recalculated, "delta": delta}
                ))

        has_critical_sensor = any(res.critical_failure for res in sensor_results.values())
        if has_critical_sensor and overall.status.value in {"VALID", "ACCEPTABLE_WITH_WARNING"}:
            checks.append(ValidationCheckResult(
                check_id="SCORE-CRITICAL-MASKED",
                category="QUALITY_SCORE",
                target="OVERALL",
                status=CheckStatus.FAILED,
                message="Critical sensor failure was masked by high aggregate session score.",
                evidence={"overall_status": overall.status.value}
            ))
        elif has_critical_sensor:
            checks.append(ValidationCheckResult(
                check_id="SCORE-CRITICAL-OVERRIDE-ACTIVE",
                category="QUALITY_SCORE",
                target="OVERALL",
                status=CheckStatus.PASSED,
                message="Critical failure override prevented session status from being VALID."
            ))

        return records, checks

    def audit_sensor_score(
        self,
        sensor_name: str,
        res: SensorQualityResult
    ) -> Tuple[ScoreAuditRecord, ValidationCheckResult]:
        m = res.metrics
        w_val = self.COMPONENT_WEIGHTS["valid_sample_ratio"]
        w_ts = self.COMPONENT_WEIGHTS["timestamp_integrity"]
        w_art = self.COMPONENT_WEIGHTS["artifact_free_ratio"]
        w_noise = self.COMPONENT_WEIGHTS["noise_score"]
        w_cont = self.COMPONENT_WEIGHTS["continuity_score"]

        artifact_free = max(0.0, 1.0 - m.artifact_ratio)
        noise_free = max(0.0, 1.0 - m.noise_index)

        c_valid = w_val * m.valid_sample_ratio
        c_ts = w_ts * m.timestamp_integrity
        c_art = w_art * artifact_free
        c_noise = w_noise * noise_free
        c_cont = w_cont * m.continuity_score

        raw_score = c_valid + c_ts + c_art + c_noise + c_cont

        has_critical = res.critical_failure or any(
            (iss.severity == IssueSeverity.CRITICAL or iss.severity.value == "CRITICAL")
            for iss in res.issues
        )
        fatal_flat = m.flatline_ratio >= 0.30
        fatal_miss = m.missing_sample_ratio >= 0.20
        fatal_ts = m.timestamp_integrity <= 0.30

        if has_critical or fatal_flat or fatal_miss or fatal_ts:
            expected_score = min(raw_score, 0.40)
        elif res.total_samples_analyzed == 0:
            expected_score = 0.0
        else:
            expected_score = raw_score

        expected_rounded = round(float(expected_score), 4)
        reported = round(float(res.quality_score), 4)
        delta = abs(reported - expected_rounded)
        is_match = delta <= 0.001

        breakdown = {
            "valid_component": round(c_valid, 4),
            "timestamp_component": round(c_ts, 4),
            "artifact_component": round(c_art, 4),
            "noise_component": round(c_noise, 4),
            "continuity_component": round(c_cont, 4),
            "raw_score": round(raw_score, 4),
            "expected_final": expected_rounded
        }

        record = ScoreAuditRecord(
            sensor=sensor_name,
            reported_score=reported,
            recalculated_score=expected_rounded,
            delta=round(delta, 6),
            is_match=is_match,
            component_breakdown=breakdown
        )

        if is_match:
            check = ValidationCheckResult(
                check_id="SCORE-SENSOR-REPRODUCED",
                category="QUALITY_SCORE",
                target=sensor_name,
                status=CheckStatus.PASSED,
                message=f"Score {reported:.4f} reproduces formula identically.",
                evidence={"reported": reported, "expected": expected_rounded, "delta": delta}
            )
        else:
            check = ValidationCheckResult(
                check_id="SCORE-SENSOR-MISMATCH",
                category="QUALITY_SCORE",
                target=sensor_name,
                status=CheckStatus.FAILED,
                message=f"Reported score ({reported:.4f}) diverges from formula reproduction ({expected_rounded:.4f}).",
                evidence={"reported": reported, "expected": expected_rounded, "delta": delta}
            )

        return record, check
