"""Cross-validator for sensor quality reports comparing JSON, LLM text, and invariants."""

import re
from typing import Dict, Any, List

try:
    from .schemas import ValidationCheckResult, CheckStatus
except ImportError:
    try:
        from schemas import ValidationCheckResult, CheckStatus
    except ImportError:
        from validation.schemas import ValidationCheckResult, CheckStatus


class CrossValidator:
    """Performs cross-validation checks between structured JSON, metrics, and LLM text."""

    def __init__(self):
        pass

    def validate_score_status_consistency(self, report_dict: Dict[str, Any]) -> List[ValidationCheckResult]:
        """Validates consistency between scores, statuses, and recommendations across sensors."""
        results: List[ValidationCheckResult] = []
        sensors_dict = report_dict.get("sensors", {})

        for sensor_name, sensor_data in sensors_dict.items():
            score = sensor_data.get("quality_score", 0.0)
            status = sensor_data.get("status", "")
            rec = sensor_data.get("recommendation", "")
            crit = sensor_data.get("critical_failure", False)

            check_id = f"SCORE_STATUS_CONSISTENCY_{sensor_name}"

            passed = True
            msg = f"{sensor_name} score={score}, status={status}, rec={rec}"

            if score >= 0.85 and status not in ("VALID", "ACCEPTABLE_WITH_WARNING", "OPERATIONAL"):
                passed = False
                msg = f"{sensor_name} high score {score} contradicts non-valid status {status}"
            elif score < 0.50 and status in ("VALID", "ACCEPTABLE_WITH_WARNING", "OPERATIONAL"):
                passed = False
                msg = f"{sensor_name} low score {score} contradicts valid status {status}"

            if crit and status not in ("CRITICAL_FAILURE", "REJECTED", "UNRELIABLE"):
                passed = False
                msg = f"{sensor_name} critical_failure is True but status is {status}"

            if status == "CRITICAL_FAILURE" and "REJECT" not in rec and "QUARANTINE" not in rec and "DISCARD" not in rec:
                passed = False
                msg = f"{sensor_name} status is CRITICAL_FAILURE but recommendation is {rec}"

            results.append(
                ValidationCheckResult(
                    check_id=check_id,
                    category="CROSS_VALIDATION",
                    target=sensor_name,
                    status=CheckStatus.PASSED if passed else CheckStatus.FAILED,
                    message=msg,
                    evidence={"score": score, "status": status, "recommendation": rec, "critical_failure": crit}
                )
            )

        return results

    def validate_evidence_issue_consistency(self, report_dict: Dict[str, Any]) -> List[ValidationCheckResult]:
        """Validates that all detected issues are backed by non-empty quantifiable evidence."""
        results: List[ValidationCheckResult] = []
        sensors_dict = report_dict.get("sensors", {})

        for sensor_name, sensor_data in sensors_dict.items():
            issues = sensor_data.get("issues", [])
            check_id = f"ISSUE_EVIDENCE_INTEGRITY_{sensor_name}"

            if not issues:
                results.append(
                    ValidationCheckResult(
                        check_id=check_id,
                        category="CROSS_VALIDATION",
                        target=sensor_name,
                        status=CheckStatus.PASSED,
                        message=f"{sensor_name} has 0 issues, status clean",
                        evidence={"issues_count": 0}
                    )
                )
                continue

            passed = True
            err_reasons = []

            for idx, issue in enumerate(issues):
                evidence = issue.get("evidence", [])
                reason_code = issue.get("reason_code", "")
                if not evidence:
                    passed = False
                    err_reasons.append(f"Issue number {idx} ({reason_code}) missing evidence records")
                else:
                    for ev in evidence:
                        if "measured_value" not in ev or "threshold_value" not in ev:
                            passed = False
                            err_reasons.append(f"Issue number {idx} evidence missing measured/threshold value")

            results.append(
                ValidationCheckResult(
                    check_id=check_id,
                    category="CROSS_VALIDATION",
                    target=sensor_name,
                    status=CheckStatus.PASSED if passed else CheckStatus.FAILED,
                    message="All issues backed by quantified evidence" if passed else "; ".join(err_reasons),
                    evidence={"issues_count": len(issues), "errors": err_reasons}
                )
            )

        return results

    def validate_json_vs_llm_consistency(self, report_dict: Dict[str, Any]) -> List[ValidationCheckResult]:
        """Checks cross-consistency between structured JSON outputs and Groq LLM executive briefing."""
        results: List[ValidationCheckResult] = []
        llm_data = report_dict.get("llm_explanation")

        if not llm_data or not isinstance(llm_data, dict):
            results.append(
                ValidationCheckResult(
                    check_id="LLM_CONSISTENCY_PRESENCE",
                    category="CROSS_VALIDATION",
                    target="llm_explanation",
                    status=CheckStatus.FAILED,
                    message="Missing llm_explanation dictionary in report",
                    evidence={}
                )
            )
            return results

        briefing = llm_data.get("briefing", "")
        if not briefing or len(briefing.strip()) < 50:
            results.append(
                ValidationCheckResult(
                    check_id="LLM_CONSISTENCY_TEXT_LENGTH",
                    category="CROSS_VALIDATION",
                    target="llm_explanation",
                    status=CheckStatus.FAILED,
                    message="LLM executive briefing is missing or trivially short",
                    evidence={"length": len(briefing)}
                )
            )
            return results

        overall_score = report_dict.get("overall_quality", {}).get("score", 0.0)
        score_pattern = rf"{overall_score:.3f}|{overall_score:.4f}"
        score_found = bool(re.search(score_pattern, briefing))

        results.append(
            ValidationCheckResult(
                check_id="LLM_CONSISTENCY_OVERALL_SCORE",
                category="CROSS_VALIDATION",
                target="llm_explanation",
                status=CheckStatus.PASSED if score_found else CheckStatus.WARNING,
                message=f"Overall score {overall_score} mentioned in LLM briefing" if score_found else f"Overall score {overall_score} not explicitly cited in LLM briefing",
                evidence={"overall_score": overall_score, "score_found": score_found}
            )
        )

        sensors_dict = report_dict.get("sensors", {})
        problematic_sensors = [s for s, d in sensors_dict.items() if len(d.get("issues", [])) > 0 or d.get("quality_score", 1.0) < 0.90]

        for sensor in problematic_sensors:
            mentioned = sensor.upper() in briefing.upper()
            results.append(
                ValidationCheckResult(
                    check_id=f"LLM_CONSISTENCY_MENTION_{sensor}",
                    category="CROSS_VALIDATION",
                    target="llm_explanation",
                    status=CheckStatus.PASSED if mentioned else CheckStatus.WARNING,
                    message=f"Degraded/flagged sensor {sensor} mentioned in LLM narrative" if mentioned else f"Sensor {sensor} has issues in JSON but was not mentioned in LLM narrative",
                    evidence={"sensor": sensor, "mentioned": mentioned}
                )
            )

        hallucinated_failures = []
        for sensor, data in sensors_dict.items():
            if data.get("quality_score", 0.0) > 0.95 and not data.get("issues"):
                pattern = rf"\b{sensor}\b.*?\b(failed|failure|rejected|corrupted|unreliable)\b"
                if re.search(pattern, briefing, re.IGNORECASE):
                    hallucinated_failures.append(sensor)

        results.append(
            ValidationCheckResult(
                check_id="LLM_CONSISTENCY_NO_HALLUCINATIONS",
                category="CROSS_VALIDATION",
                target="llm_explanation",
                status=CheckStatus.PASSED if not hallucinated_failures else CheckStatus.FAILED,
                message="No hallucinated sensor failures detected in LLM text" if not hallucinated_failures else f"LLM narrative claimed failure for healthy sensors: {hallucinated_failures}",
                evidence={"hallucinated_failures": hallucinated_failures}
            )
        )

        return results

    def validate_decision_critical_invariants(self, report_dict: Dict[str, Any]) -> List[ValidationCheckResult]:
        """Validates that downstream processing decisions satisfy mission safety invariants."""
        results: List[ValidationCheckResult] = []
        decision = report_dict.get("processing_decision", {})
        can_proceed = decision.get("can_proceed", False)
        sensors_dict = report_dict.get("sensors", {})

        critical_sensors = {"ECG", "RESP"}
        critical_failed = [s for s, d in sensors_dict.items() if s in critical_sensors and (d.get("critical_failure", False) or d.get("quality_score", 0.0) < 0.30)]

        if critical_failed and can_proceed:
            results.append(
                ValidationCheckResult(
                    check_id="DECISION_CRITICAL_FAILURE_INVARIANT",
                    category="CROSS_VALIDATION",
                    target="processing_decision",
                    status=CheckStatus.FAILED,
                    message=f"Critical sensor failure ({critical_failed}) but downstream decision can_proceed=True",
                    evidence={"critical_failed": critical_failed, "can_proceed": can_proceed}
                )
            )
        else:
            results.append(
                ValidationCheckResult(
                    check_id="DECISION_CRITICAL_FAILURE_INVARIANT",
                    category="CROSS_VALIDATION",
                    target="processing_decision",
                    status=CheckStatus.PASSED,
                    message="Critical sensor failure invariant respected",
                    evidence={"critical_failed": critical_failed, "can_proceed": can_proceed}
                )
            )

        overall_score = report_dict.get("overall_quality", {}).get("score", 0.0)
        if overall_score < 0.50 and can_proceed:
            results.append(
                ValidationCheckResult(
                    check_id="DECISION_MINIMUM_SCORE_INVARIANT",
                    category="CROSS_VALIDATION",
                    target="processing_decision",
                    status=CheckStatus.FAILED,
                    message=f"Overall score {overall_score} < 0.50 but can_proceed=True",
                    evidence={"overall_score": overall_score, "can_proceed": can_proceed}
                )
            )
        else:
            results.append(
                ValidationCheckResult(
                    check_id="DECISION_MINIMUM_SCORE_INVARIANT",
                    category="CROSS_VALIDATION",
                    target="processing_decision",
                    status=CheckStatus.PASSED,
                    message="Session overall score invariant respected",
                    evidence={"overall_score": overall_score, "can_proceed": can_proceed}
                )
            )

        return results

    def run_all_cross_validations(self, report_dict: Dict[str, Any]) -> List[ValidationCheckResult]:
        """Executes all cross-validation checks."""
        results = []
        results.extend(self.validate_score_status_consistency(report_dict))
        results.extend(self.validate_evidence_issue_consistency(report_dict))
        results.extend(self.validate_json_vs_llm_consistency(report_dict))
        results.extend(self.validate_decision_critical_invariants(report_dict))
        return results
