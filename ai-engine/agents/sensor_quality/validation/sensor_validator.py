"""Independent validator for sensor-level outputs, consistency rules, and issue evidence."""
from typing import Dict, List, Tuple
try:
    from ..schemas.signal_schema import QualityStatus, IssueSeverity
    from ..schemas.output_schema import SensorQualityResult, DetectedIssue
    from .schemas import ValidationCheckResult, CheckStatus, SensorValidationSummary
except ImportError:
    try:
        from schemas.signal_schema import QualityStatus, IssueSeverity
        from schemas.output_schema import SensorQualityResult, DetectedIssue
        from validation.schemas import ValidationCheckResult, CheckStatus, SensorValidationSummary
    except ImportError:
        from sensor_quality.schemas.signal_schema import QualityStatus, IssueSeverity
        from sensor_quality.schemas.output_schema import SensorQualityResult, DetectedIssue
        from sensor_quality.validation.schemas import ValidationCheckResult, CheckStatus, SensorValidationSummary

class SensorOutputValidator:
    """Validates structural and logical integrity of sensor-level agent results."""

    APPROVED_STATUSES = {
        QualityStatus.VALID.value,
        QualityStatus.ACCEPTABLE_WITH_WARNING.value,
        QualityStatus.DEGRADED.value,
        QualityStatus.INVALID.value,
        QualityStatus.INSUFFICIENT_DATA.value
    }

    STATUS_RECOMMENDATION_MAP = {
        QualityStatus.VALID.value: "ACCEPT",
        QualityStatus.ACCEPTABLE_WITH_WARNING.value: "ACCEPT_WITH_WARNING",
        QualityStatus.DEGRADED.value: "FLAG_DEGRADED",
        QualityStatus.INVALID.value: "REJECT",
        QualityStatus.INSUFFICIENT_DATA.value: "REJECT"
    }

    def validate_sensor_results(
        self,
        sensor_results: Dict[str, SensorQualityResult]
    ) -> Tuple[List[ValidationCheckResult], Dict[str, SensorValidationSummary]]:
        checks: List[ValidationCheckResult] = []
        summaries: Dict[str, SensorValidationSummary] = {}

        if not sensor_results:
            checks.append(ValidationCheckResult(
                check_id="SENSOR-EMPTY-RESULTS",
                category="SENSOR_OUTPUT",
                target="ALL",
                status=CheckStatus.FAILED,
                message="No sensor quality results found in report."
            ))
            return checks, summaries

        for sensor_name, result in sensor_results.items():
            sensor_checks, summary = self.validate_single_sensor(sensor_name, result)
            checks.extend(sensor_checks)
            summaries[sensor_name] = summary

        return checks, summaries

    def validate_single_sensor(
        self,
        sensor_name: str,
        result: SensorQualityResult
    ) -> Tuple[List[ValidationCheckResult], SensorValidationSummary]:
        checks: List[ValidationCheckResult] = []
        target = sensor_name.upper()

        score = result.quality_score
        if not isinstance(score, (int, float)) or score < 0.0 or score > 1.0:
            checks.append(ValidationCheckResult(
                check_id="SENSOR-SCORE-BOUNDS",
                category="SENSOR_OUTPUT",
                target=target,
                status=CheckStatus.FAILED,
                message=f"Quality score ({score}) outside bounded domain [0.0, 1.0].",
                evidence={"score": score}
            ))
        else:
            checks.append(ValidationCheckResult(
                check_id="SENSOR-SCORE-BOUNDS",
                category="SENSOR_OUTPUT",
                target=target,
                status=CheckStatus.PASSED,
                message=f"Quality score within bounded domain: {score}",
                evidence={"score": score}
            ))

        status_str = result.status.value if hasattr(result.status, "value") else str(result.status)
        if status_str not in self.APPROVED_STATUSES:
            checks.append(ValidationCheckResult(
                check_id="SENSOR-STATUS-ENUM",
                category="SENSOR_OUTPUT",
                target=target,
                status=CheckStatus.FAILED,
                message=f"Status '{status_str}' not in approved enum {self.APPROVED_STATUSES}."
            ))
        else:
            checks.append(ValidationCheckResult(
                check_id="SENSOR-STATUS-ENUM",
                category="SENSOR_OUTPUT",
                target=target,
                status=CheckStatus.PASSED,
                message=f"Status is valid enum value: {status_str}"
            ))

        expected_rec = self.STATUS_RECOMMENDATION_MAP.get(status_str)
        if result.recommendation != expected_rec:
            checks.append(ValidationCheckResult(
                check_id="SENSOR-STATUS-REC-INCONSISTENT",
                category="SENSOR_OUTPUT",
                target=target,
                status=CheckStatus.FAILED,
                message=f"Recommendation '{result.recommendation}' does not match status '{status_str}' (expected '{expected_rec}').",
                evidence={"status": status_str, "recommendation": result.recommendation, "expected": expected_rec}
            ))
        else:
            checks.append(ValidationCheckResult(
                check_id="SENSOR-STATUS-REC-CONSISTENT",
                category="SENSOR_OUTPUT",
                target=target,
                status=CheckStatus.PASSED,
                message="Recommendation matches status definition."
            ))

        has_critical = result.critical_failure or any(
            (iss.severity == IssueSeverity.CRITICAL or iss.severity.value == "CRITICAL")
            for iss in result.issues
        )
        if has_critical and status_str in {QualityStatus.VALID.value, QualityStatus.ACCEPTABLE_WITH_WARNING.value}:
            checks.append(ValidationCheckResult(
                check_id="SENSOR-CRITICAL-INVARIANT-VIOLATED",
                category="SENSOR_OUTPUT",
                target=target,
                status=CheckStatus.FAILED,
                message=f"Sensor flagged with critical failure but marked '{status_str}'. Invariant violated.",
                evidence={"critical_failure": result.critical_failure, "status": status_str}
            ))
        elif has_critical:
            checks.append(ValidationCheckResult(
                check_id="SENSOR-CRITICAL-INVARIANT-SATISFIED",
                category="SENSOR_OUTPUT",
                target=target,
                status=CheckStatus.PASSED,
                message="Critical failure correctly forced status to INVALID/DEGRADED."
            ))

        has_warning_issue = any(
            (iss.severity in {IssueSeverity.MODERATE, IssueSeverity.HIGH} or iss.severity.value in {"MODERATE", "HIGH"})
            for iss in result.issues
        )
        if has_warning_issue and status_str == QualityStatus.VALID.value:
            checks.append(ValidationCheckResult(
                check_id="SENSOR-WARNING-MASKED",
                category="SENSOR_OUTPUT",
                target=target,
                status=CheckStatus.WARNING,
                message="Sensor has active moderate/high issues but was marked fully VALID without warning (advisable to refine status threshold to ACCEPTABLE_WITH_WARNING).",
                evidence={"issues": [i.reason_code for i in result.issues]}
            ))

        issue_checks = self._validate_issues(target, result.issues)
        checks.extend(issue_checks)

        verdict_str = "PASSED" if not any(c.status == CheckStatus.FAILED for c in checks) else "FAILED"
        notes_list = [c.message for c in checks if c.status in {CheckStatus.FAILED, CheckStatus.WARNING}]
        summary = SensorValidationSummary(
            sensor=target,
            quality_score=float(score),
            status=status_str,
            recommendation=result.recommendation,
            critical_failure=bool(result.critical_failure),
            issue_count=len(result.issues),
            verdict=verdict_str,
            notes="; ".join(notes_list) if notes_list else "All checks passed."
        )

        return checks, summary

    def _validate_issues(self, sensor: str, issues: List[DetectedIssue]) -> List[ValidationCheckResult]:
        checks = []
        for idx, iss in enumerate(issues):
            if not iss.evidence:
                checks.append(ValidationCheckResult(
                    check_id="ISSUE-NO-EVIDENCE",
                    category="SENSOR_OUTPUT",
                    target=sensor,
                    status=CheckStatus.WARNING,
                    message=f"Issue {iss.reason_code} has no empirical evidence entries.",
                    evidence={"reason_code": iss.reason_code}
                ))
            else:
                for ev in iss.evidence:
                    if not isinstance(ev.measured_value, (int, float)) or not isinstance(ev.threshold_value, (int, float)):
                        checks.append(ValidationCheckResult(
                            check_id="ISSUE-EVIDENCE-NON-NUMERIC",
                            category="SENSOR_OUTPUT",
                            target=sensor,
                            status=CheckStatus.FAILED,
                            message=f"Evidence for {iss.reason_code} contains non-numeric measured/threshold values."
                        ))

            if iss.time_interval:
                if iss.time_interval.start > iss.time_interval.end:
                    checks.append(ValidationCheckResult(
                        check_id="ISSUE-INTERVAL-INVALID",
                        category="SENSOR_OUTPUT",
                        target=sensor,
                        status=CheckStatus.FAILED,
                        message=f"Issue {iss.reason_code} has invalid time interval: start ({iss.time_interval.start}) > end ({iss.time_interval.end})."
                    ))
        return checks
