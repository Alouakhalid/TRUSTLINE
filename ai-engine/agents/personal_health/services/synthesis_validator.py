"""Clinical synthesis validation layer enforcing evidence-grounding and claim audit."""
import re
from typing import Dict, List, Optional, Tuple, Any
from pydantic import BaseModel, Field

class ClaimValidationItem(BaseModel):
    """Individual assertion evaluated for clinical grounding and evidence provenance."""
    claim_text: str
    evidence_references: List[str] = Field(default_factory=list)
    evidence_source: str = Field(default="ground_truth_context")
    support_status: str = Field(default="supported", description="supported | partially_supported | unsupported")
    rejection_reason: Optional[str] = None

class SynthesisValidationResult(BaseModel):
    """Aggregate audit verdict of generated clinical briefing."""
    is_valid: bool
    claims: List[ClaimValidationItem] = Field(default_factory=list)
    rejection_reasons: List[str] = Field(default_factory=list)
    sanitized_synthesis: str

    @property
    def rejections(self) -> List[str]:
        """Convenience alias for rejection_reasons list."""
        return self.rejection_reasons

class ClinicalSynthesisValidator:
    """Pre-output validation engine detecting clinical hallucinations and scope overclaims."""

    def validate_synthesis(
        self,
        synthesis_text: str,
        ground_truth: Dict[str, Any]
    ) -> SynthesisValidationResult:
        """Evaluate clinical assertions against ground-truth data boundaries."""
        claims: List[ClaimValidationItem] = []
        rejections: List[str] = []

        lower = synthesis_text.lower()

        rmssd_val = ground_truth.get("rmssd_value", 0.0)
        rmssd_status = ground_truth.get("rmssd_status", "invalid")
        if rmssd_val < 1.0 or rmssd_status in ("invalid", "insufficient_variance"):
            unsupported_rmssd_patterns = [
                r"rmssd\s+(?:is\s+)?(?:within normal|normal|preserved|nominal|healthy)",
                r"(?:normal|nominal|preserved|healthy)\s+rmssd",
                r"hrv\s+(?:is\s+)?(?:within normal|normal|preserved|nominal|healthy)",
                r"(?:normal|nominal|preserved|healthy)\s+hrv",
                r"(?:normal|preserved|nominal|healthy|effective)\s+(?:autonomic|parasympathetic|vagal)\s+tone",
                r"parasympathetic\s+tone\s+(?:is\s+)?(?:normal|preserved|nominal|healthy|effective)"
            ]
            for pat in unsupported_rmssd_patterns:
                if re.search(pat, lower):
                    rejection = f"Unsupported claim: RMSSD={rmssd_val} ms is invalid/unvarying, but synthesis claimed it was normal or preserved parasympathetic tone."
                    rejections.append(rejection)
                    claims.append(ClaimValidationItem(
                        claim_text=pat,
                        support_status="unsupported",
                        rejection_reason=rejection
                    ))

        direct_vagal_patterns = [
            r"direct(?:ly)?\s+(?:measur|record|assess)\w*\s+(?:of\s+)?(?:the\s+)?vagus",
            r"direct\s+vagal\s+(?:nerve\s+)?(?:measurement|recording)",
            r"direct\s+electromechanical\s+recording\s+of\s+the\s+vagus"
        ]
        for pat in direct_vagal_patterns:
            if re.search(pat, lower):
                rejection = "Physiological overclaim: RMSSD was asserted as a direct electromechanical measurement of the vagus nerve rather than a surrogate index associated with cardiac autonomic regulation."
                rejections.append(rejection)
                claims.append(ClaimValidationItem(
                    claim_text=pat,
                    support_status="unsupported",
                    rejection_reason=rejection
                ))

        if not ground_truth.get("has_clinical_fluid_shift_evidence", False):
            if re.search(r"fluid\s+(?:redistribution|shift)", lower) or "cephalad" in lower:
                rejection = "Unsupported causal claim: Cephalad fluid redistribution asserted without explicit diagnostic confirmation in input data."
                rejections.append(rejection)
                claims.append(ClaimValidationItem(
                    claim_text="fluid redistribution / cephalad shift",
                    support_status="unsupported",
                    rejection_reason=rejection
                ))

        mission_day = ground_truth.get("mission_day")
        if mission_day is None:
            day_matches = re.findall(r"(?:mission\s+day|flight\s+day|fd\s*|day\s+)(\d+(?:\.\d+)?)", lower)
            if day_matches:
                rejection = f"Unsupported mission context claim: Mentioned Mission Day {day_matches[0]} when mission elapsed time was not supplied."
                rejections.append(rejection)
                claims.append(ClaimValidationItem(
                    claim_text=f"Day {day_matches[0]}",
                    support_status="unsupported",
                    rejection_reason=rejection
                ))

        symptom_count = ground_truth.get("symptom_count", 0)
        symptom_confirmed_negative = ground_truth.get("symptom_confirmed_negative", False)
        if symptom_count == 0 and not symptom_confirmed_negative:
            for pat in [r"\bhas no symptoms\b", r"\bfree of symptoms\b", r"\bwithout symptoms\b"]:
                if re.search(pat, lower):
                    rejection = f"Unsupported symptom claim: Telemetry session had zero reported symptoms, but synthesis claimed '{pat}'."
                    rejections.append(rejection)
                    claims.append(ClaimValidationItem(
                        claim_text=pat,
                        support_status="unsupported",
                        rejection_reason=rejection
                    ))
            if "asymptomatic" in lower:
                negated_phrases = [
                    "cannot be confirmed as asymptomatic",
                    "not confirmed as asymptomatic",
                    "does not mean asymptomatic",
                    "does not confirm asymptomatic",
                    "not necessarily asymptomatic",
                    "not verified as asymptomatic",
                    "not confirmed that the astronaut is asymptomatic"
                ]
                if not any(np in lower for np in negated_phrases):
                    rejection = "Unsupported symptom claim: Telemetry session had zero reported symptoms, which was falsely converted into a confirmed asymptomatic assessment."
                    rejections.append(rejection)
                    claims.append(ClaimValidationItem(
                        claim_text="asymptomatic",
                        support_status="unsupported",
                        rejection_reason=rejection
                    ))
            if "absence of symptoms" in lower:
                negated_absence = [
                    "does not constitute",
                    "does not confirm",
                    "cannot be confirmed",
                    "not confirmed",
                    "unverified",
                    "lack of reported symptoms does not"
                ]
                if not any(na in lower for na in negated_absence):
                    rejection = "Unsupported symptom claim: Telemetry session had zero reported symptoms, which was falsely converted into a confirmed absence of symptoms."
                    rejections.append(rejection)
                    claims.append(ClaimValidationItem(
                        claim_text="absence of symptoms",
                        support_status="unsupported",
                        rejection_reason=rejection
                    ))

        unsupported_stability_patterns = [
            r"psychologically stable",
            r"psychological and physiological stability",
            r"medically stable",
            r"state of physiological homeostasis",
            r"overall health is nominal",
            r"overall psychological stability"
        ]
        for pat in unsupported_stability_patterns:
            if re.search(pat, lower):
                rejection = f"ML scope violation: WESAD stress model output was overclaimed as evidence of broad clinical/psychological stability ({pat})."
                rejections.append(rejection)
                claims.append(ClaimValidationItem(
                    claim_text=pat,
                    support_status="unsupported",
                    rejection_reason=rejection
                ))

        baseline_status = ground_truth.get("baseline_status", "not_available")
        if baseline_status != "available":
            unsupported_baseline_patterns = [
                r"(?:recommend|suggest|approve|advise)\w*\s+(?:registering|saving|using|adopting)?\s*(?:this|current)?\s*(?:session|data|telemetry)?\s*(?:as|for)\s+(?:a\s+)?(?:personal\s+)?baseline",
                r"registers?\s+(?:this|current)\s+session\s+as\s+(?:a\s+)?(?:personal\s+)?baseline",
                r"(?:against|to|with)\s+(?:the|an|his|her|their)\s+established\s+(?:personal\s+)?baseline",
                r"within\s+(?:the\s+)?established\s+(?:personal\s+)?baseline",
                r"deviat\w+\s+from\s+(?:the\s+)?established\s+(?:personal\s+)?baseline"
            ]
            for pat in unsupported_baseline_patterns:
                if re.search(pat, lower):
                    rejection = "Baseline boundary violation: Personal baseline status is not_available, but synthesis referenced an established baseline or recommended automatic baseline registration."
                    rejections.append(rejection)
                    claims.append(ClaimValidationItem(
                        claim_text=pat,
                        support_status="unsupported",
                        rejection_reason=rejection
                    ))

        if not ground_truth.get("has_resp_measurement", True):
            if "respiratory rate" in lower or "breathing rate" in lower or "breathing pattern" in lower:
                rejection = "Invented measurement: Respiration discussed without valid sensor extraction."
                rejections.append(rejection)
                claims.append(ClaimValidationItem(
                    claim_text="respiration",
                    support_status="unsupported",
                    rejection_reason=rejection
                ))

        if not ground_truth.get("has_acc_measurement", True):
            if "motor activity" in lower or "locomotion" in lower or "acceleromet" in lower:
                rejection = "Invented measurement: Motor activity discussed without valid accelerometry extraction."
                rejections.append(rejection)
                claims.append(ClaimValidationItem(
                    claim_text="motor activity",
                    support_status="unsupported",
                    rejection_reason=rejection
                ))

        escalation_status = ground_truth.get("escalation_status", "NO_TRIGGER_DETECTED")
        if escalation_status in ("INSUFFICIENT_DATA", "ESCALATION_REQUIRED", "ASSESSMENT_FAILED"):
            nominal_emergency_patterns = [
                r"emergency\s+(?:escalation\s+)?(?:status\s+)?(?:is\s+)?nominal",
                r"emergency\s+(?:is\s+)?ruled\s+out",
                r"rules?\s+out\s+(?:an?\s+)?emergency",
                r"absence\s+of\s+emergency"
            ]
            for pat in nominal_emergency_patterns:
                if re.search(pat, lower):
                    rejection = f"Emergency status discrepancy: Deterministic escalation status is {escalation_status}, but synthesis claimed emergency status is nominal or ruled out."
                    rejections.append(rejection)
                    claims.append(ClaimValidationItem(
                        claim_text=pat,
                        support_status="unsupported",
                        rejection_reason=rejection
                    ))

        is_valid = len(rejections) == 0
        sanitized = synthesis_text if is_valid else self.generate_grounded_fallback(ground_truth)

        return SynthesisValidationResult(
            is_valid=is_valid,
            claims=claims,
            rejection_reasons=rejections,
            sanitized_synthesis=sanitized
        )

    def generate_grounded_fallback(self, ground_truth: Dict[str, Any]) -> str:
        """Construct a strictly grounded, deterministic clinical synthesis without unevidenced claims."""
        astronaut_id = ground_truth.get("astronaut_id", "UNKNOWN")
        session_id = ground_truth.get("session_id", "UNKNOWN")
        hr = ground_truth.get("hr_value", 72.0)
        rmssd = ground_truth.get("rmssd_value", 0.0)
        rmssd_status = ground_truth.get("rmssd_status", "insufficient_variance")
        eda = ground_truth.get("eda_value", 4.69)
        hgb_prob = ground_truth.get("hgb_prob", 0.1201)
        hgb_verdict = ground_truth.get("hgb_verdict", "NORMAL")
        symptom_count = ground_truth.get("symptom_count", 0)
        baseline_status = ground_truth.get("baseline_status", "not_available")
        escalation_status = ground_truth.get("escalation_status", "NO_TRIGGER_DETECTED")

        if rmssd < 1.0 or rmssd_status in ("invalid", "insufficient_variance", "zero_variability"):
            hrv_sentence = (
                f"The computed cardiac HRV RMSSD is {rmssd:.1f} ms. "
                f"Constant RR intervals and zero variability were observed in this input. "
                f"The signal is unsuitable for meaningful HRV interpretation. This observation alone does not establish the physiological cause."
            )
        else:
            hrv_sentence = (
                f"The computed cardiac HRV RMSSD is {rmssd:.1f} ms, serving as a surrogate index associated with cardiac autonomic regulation."
            )

        p1 = (
            f"Objective physiological telemetry for Astronaut {astronaut_id} (Session {session_id}) recorded a mean "
            f"heart rate of {hr:.1f} bpm and mean skin conductance of {eda:.2f} uS. "
            f"{hrv_sentence}"
        )

        if symptom_count == 0:
            symptom_sentence = (
                "No symptoms were recorded in the provided assessment. "
                "Lack of recorded symptoms does not constitute a confirmed negative clinical assessment."
            )
        else:
            symptom_sentence = f"Subjective symptom records contain {symptom_count} entries for clinical evaluation."

        p2 = (
            f"The WESAD-trained HistGradientBoosting classifier produced an acute stress probability of {hgb_prob:.4f} "
            f"(verdict: {hgb_verdict}). This model is validated strictly within experimental laboratory stress induction "
            f"benchmarks and does not assess general medical fitness, organic pathology, or long-term psychological adaptation. "
            f"{symptom_sentence}"
        )

        if escalation_status == "ESCALATION_REQUIRED":
            escalation_sentence = "Emergency escalation status is ESCALATION_REQUIRED. Immediate high-priority clinical intervention and medical review are indicated."
        elif escalation_status == "INSUFFICIENT_DATA":
            escalation_sentence = "Emergency escalation status is INSUFFICIENT_DATA due to missing or unvalidated physiological telemetry; physiological emergency cannot be conclusively ruled out and close telemetry monitoring is advised."
        elif escalation_status == "ASSESSMENT_FAILED":
            escalation_sentence = "Emergency escalation status is ASSESSMENT_FAILED due to an internal computational exception; manual clinical telemetry review is indicated."
        else:
            escalation_sentence = "Emergency escalation status is NO_TRIGGER_DETECTED with no configured escalation rule triggered using the available telemetry. This observation alone does not confirm that the astronaut is medically normal or that no health risk exists."

        p3 = (
            f"Individualized personal baseline status is '{baseline_status}'; comparative baseline deviation analysis was not performed. "
            f"This session represents an isolated observation and must not be registered as an established personal baseline. "
            f"{escalation_sentence}"
        )

        return f"{p1}\n\n{p2}\n\n{p3}"
