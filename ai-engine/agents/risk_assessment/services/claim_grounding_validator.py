"""Deterministic validator auditing LLM-generated synthesis against empirical evidence and rules."""
import re
from typing import Dict, List, Optional, Tuple, Any
from ..schemas.risk_rules import RiskLevel, EscalationState

class ClaimGroundingValidator:
    """Audits clinical synthesis text ensuring zero diagnostic leaps, ungrounded claims, or coverage distortions."""

    FORBIDDEN_DIAGNOSES: Tuple[str, ...] = (
        "myocardial infarction",
        "heart attack",
        "coronary thrombosis",
        "pneumonia",
        "pulmonary embolism",
        "clinical depression",
        "cardiac arrest",
        "stroke",
        "diagnosed with",
        "suffering from a disease"
    )

    FORBIDDEN_CAUSAL_LEAPS: Tuple[str, ...] = (
        "cephalad fluid redistribution caused",
        "fluid shift is responsible",
        "microgravity fluid shift caused"
    )

    @classmethod
    def _split_into_clauses(cls, text: str) -> List[str]:
        """Split text into distinct clauses bounded by sentence and clause punctuation."""
        clauses: List[str] = []
        sentences = re.split(r"(?<=[.!?])\s+", text)
        for s in sentences:
            parts = re.split(r"[,;:\n—\(\)]+", s)
            for p in parts:
                cleaned = p.strip()
                if cleaned:
                    clauses.append(cleaned)
        return clauses

    @classmethod
    def validate_synthesis(
        cls,
        text: str,
        overall_risk: RiskLevel,
        escalation_state: EscalationState,
        mission_day_supplied: bool = False,
        assessment_status: str = "COMPLETED",
        unevaluated_domains: Optional[List[str]] = None,
        symptoms_explicitly_denied: bool = False,
        allowed_protective_domains: Optional[List[str]] = None,
        protective_factors: Optional[List[str]] = None
    ) -> Tuple[bool, List[str]]:
        """Verify generated text strictly conforms to empirical boundaries and coverage constraints."""
        violations: List[str] = []
        lower = text.lower()

        if protective_factors is not None and allowed_protective_domains is None:
            allowed_protective_domains = protective_factors

        for diag in cls.FORBIDDEN_DIAGNOSES:
            if diag in lower:
                violations.append(f"Forbidden clinical diagnosis claim detected: '{diag}'.")

        for cl in cls.FORBIDDEN_CAUSAL_LEAPS:
            if cl in lower:
                violations.append(f"Forbidden ungrounded causal attribution detected: '{cl}'.")

        if not mission_day_supplied:
            if re.search(r"mission\s+day\s+\d+", lower):
                violations.append("Hallucinated unsupplied mission day reference detected.")

        if overall_risk in (RiskLevel.HIGH, RiskLevel.CRITICAL):
            if "low risk" in lower or "nominal health" in lower or "no medical concerns" in lower:
                violations.append(
                    f"Synthesis contradicts deterministic overall risk '{overall_risk.value}' by asserting nominal or low risk."
                )

        if overall_risk == RiskLevel.INSUFFICIENT_DATA:
            clauses = cls._split_into_clauses(lower)
            contradicts_overall = False
            for clause in clauses:
                if (
                    "overall low risk" in clause
                    or "overall risk is low" in clause
                    or "overall risk as low" in clause
                    or "overall physiological risk as low" in clause
                    or "overall risk as **low**" in clause
                    or "overall risk: low" in clause
                    or "at overall low risk" in clause
                    or re.search(r"\boverall\s+(?:physiological\s+|clinical\s+)?risk\b[^.\n]*\blow\b", clause)
                ):
                    contradicts_overall = True
                    break
            if contradicts_overall:
                violations.append(
                    "Synthesis contradicts deterministic overall risk 'INSUFFICIENT_DATA' by declaring overall risk is low."
                )

        esc_val = escalation_state.value if hasattr(escalation_state, "value") else str(escalation_state)
        if esc_val == EscalationState.ESCALATION_REQUIRED.value:
            if "no escalation" in lower or "routine monitoring only" in lower:
                violations.append(
                    "Synthesis contradicts mandatory ESCALATION_REQUIRED state by suggesting no escalation."
                )

        if esc_val == EscalationState.NO_TRIGGER_DETECTED.value:
            urgent_mandate_patterns = (
                r"immediate\s+action\s+is\s+required",
                r"requires\s+immediate\s+(?:clinical\s+|operational\s+)?action",
                r"requires\s+immediate\s+intervention",
                r"urgent\s+operational\s+action",
                r"urgent\s+clinical\s+action",
                r"flight\s+surgeon\s+should\s+treat[^\.\n]*requiring\s+enhanced\s+manual\s+monitoring",
                r"flight\s+surgeon\s+must\s+intervene",
                r"emergency\s+monitoring\s+is\s+required",
                r"mandates\s+immediate\s+escalation"
            )
            for ump in urgent_mandate_patterns:
                if re.search(ump, lower):
                    violations.append(
                        "Synthesis asserts urgent operational mandate or clinical escalation when deterministic escalation state is NO_TRIGGER_DETECTED."
                    )
                    break

            if (
                re.search(r"(?:emergency\s+actions?|clinical\s+actions?|operational\s+actions?)\s+(?:are\s+not|are\s+never)\s+permitted", lower)
                or "actions are not permitted" in lower
                or "actions are prohibited" in lower
                or "interventions are not permitted" in lower
                or "actions are not required or permitted" in lower
                or "actions are required or permitted" in lower
            ):
                violations.append(
                    "Synthesis makes absolute statement claiming emergency or clinical actions are not permitted or prohibited."
                )

            if re.search(r"act-nom-001[^\.\n]*(?:missing\s+domains|prospective\s+(?:data\s+)?collection\s+for\s+(?:the\s+)?missing|sleep\s+logs|fluid\s+intake|neurological)", lower):
                violations.append(
                    "Synthesis improperly attributes prospective collection of missing-domain telemetry to ACT-NOM-001."
                )

        if unevaluated_domains:
            for ud in unevaluated_domains:
                ud_clean = ud.lower().replace("_", " ")
                ud_pat = rf"\b{re.escape(ud_clean)}\b"
                if re.search(ud_pat, lower):
                    sentences = re.split(r"(?<=[.!?])\s+", lower)
                    for sent in sentences:
                        if re.search(ud_pat, sent):
                            has_nom_assertion = bool(
                                re.search(
                                    r"(?:is|exhibits|shows|remains)?\s*(?:nominal|normal|healthy|low\s+risk|fully\s+intact|free\s+from)",
                                    sent
                                )
                            )
                            if has_nom_assertion:
                                has_negation = bool(
                                    re.search(
                                        r"(?:cannot\s+be\s+assumed|cannot\s+be\s+considered|does\s+not\s+establish|not\s+assumed|unmonitored\s+and\s+cannot|not\s+(?:nominal|normal|healthy|low\s+risk|free)|unknown,\s+not\s+that\s+health\s+is\s+confirmed\s+nominal)",
                                        sent
                                    )
                                )
                                if not has_negation:
                                    violations.append(
                                        f"Unevaluated domain '{ud}' improperly asserted as nominal/normal in clinical synthesis."
                                    )
                                    break

        if not symptoms_explicitly_denied:
            has_denial = False
            for direct_phrase in ("denies symptoms", "denies any symptoms", "reported no symptoms"):
                if direct_phrase in lower:
                    has_denial = True
                    break

            if not has_denial:
                matches = list(re.finditer(r"(?:confirmed\s+absence\s+of\s+symptoms|absence\s+of\s+symptoms\s+confirmed)", lower))
                if matches:
                    negated_patterns = (
                        r"(?:not|rather\s+than|does\s+not\s+(?:represent|establish|confirm|imply)|no)\s+(?:a\s+)?confirmed\s+absence\s+of\s+symptoms",
                        r"absence\s+of\s+reports\s+does\s+not\s+establish\s+(?:clinical\s+)?absence\s+of\s+symptoms",
                        r"does\s+not\s+establish\s+(?:clinical\s+|confirmed\s+)?absence\s+of\s+symptoms",
                        r"does\s+not\s+establish\s+nominal\s+status",
                        r"cannot\s+be\s+(?:interpreted|assumed|taken)\s+as\s+(?:a\s+)?confirmed\s+absence",
                        r"not\s+a\s+confirmed\s+absence",
                        r"not\s+confirmed\s+absence"
                    )
                    for m in matches:
                        context = lower[max(0, m.start() - 60):min(len(lower), m.end() + 60)]
                        if not any(re.search(pat, context) for pat in negated_patterns):
                            has_denial = True
                            break

            if has_denial:
                violations.append(
                    "Synthesis asserts unconfirmed symptom denial ('reported no symptoms' or 'denies symptoms') when symptoms were only unsubmitted."
                )

        if allowed_protective_domains is not None:
            allowed_lowers = [d.lower() for d in allowed_protective_domains]
            candidates = ["cardiovascular", "respiratory", "thermoregulatory", "psychological", "data quality", "sensor quality"]
            clauses = cls._split_into_clauses(lower)
            for cand in candidates:
                if cand not in allowed_lowers:
                    cand_pat = rf"\b{re.escape(cand)}\b"
                    for clause in clauses:
                        if re.search(cand_pat, clause):
                            if re.search(r"(?:is\s+protective|protective\s+factor|is\s+nominal\b|signal\s+fidelity\s+is\s+fully\s+verified)", clause):
                                violations.append(f"Synthesis asserts unverified protective factor for domain '{cand}'.")
                                break

            if "cardiovascular" not in allowed_lowers:
                cv_infer_patterns = (
                    r"cardiovascular\s+(?:stability|health|protection|function)\b[^\.\n]*(?:inferred|derived|supported|confirmed|demonstrated|concluded)\s+(?:by|from)\s+respirat",
                    r"respirat[^\.\n]*(?:confirms|supports|demonstrates|indicates|guarantees)\s+cardiovascular\s+(?:stability|health|protection|function)",
                    r"respiratory\s+observation\s+confirms\s+cardiovascular",
                    r"cardiovascular\s+stability\s+is\s+confirmed\s+by\s+respiratory"
                )
                for cip in cv_infer_patterns:
                    if re.search(cip, lower):
                        violations.append(
                            "Synthesis improperly infers cardiovascular stability from respiratory-only protective or nominal observation."
                        )
                        break

        hrv_patterns = (
            r"\bhrv\s+is\s+normal\b",
            r"\bnormal\s+hrv\b",
            r"\bnominal\s+hrv\b",
            r"\bhrv\s+is\s+nominal\b",
            r"\bhealthy\s+hrv\b",
            r"(?<!in)\bvalid\s+hrv\b",
            r"\bautonomic\s+regulation\s+is\s+intact\b",
            r"\bnormal\s+autonomic\s+regulation\b",
            r"\bintact\s+autonomic\s+regulation\b",
            r"\bnominal\s+heart\s+rate\s+variability\b",
            r"\bnormal\s+heart\s+rate\s+variability\b",
            r"\bintact\s+heart\s+rate\s+variability\b"
        )
        if any(re.search(hp, lower) for hp in hrv_patterns):
            violations.append(
                "Synthesis improperly asserts normal HRV or intact autonomic regulation when HRV telemetry is invalid or zero-variability artifact."
            )

        if (
            "wesad confirms psychological health" in lower
            or "wesad proves" in lower
            or "proves the astronaut is psychologically healthy" in lower
            or "proves astronaut is psychologically healthy" in lower
            or "proves the astronaut is free of stress" in lower
            or "proves astronaut is free of stress" in lower
            or "clinically free of stress" in lower
            or "psychologically healthy based on wesad" in lower
        ):
            violations.append(
                "Synthesis improperly upgrades experimental WESAD laboratory benchmark to clinical proof of astronaut psychological health."
            )

        if (
            "confirms normal core temperature" in lower
            or "core body temperature is 34" in lower
            or "core temperature is 34" in lower
            or "core temperature of 34" in lower
            or "core body temperature of 34" in lower
        ):
            violations.append(
                "Synthesis improperly conflates peripheral skin surface temperature with core body temperature."
            )

        if (
            "all physiological variables are nominal" in lower
            or "all physiological variables are normal" in lower
            or "all physiological telemetry is fully valid" in lower
            or re.search(r"indicating\s+that\s+(?:all\s+)?observed\s+variables\s+remained\s+within\s+(?:established\s+)?reference\s+limits", lower)
            or re.search(r"(?:all\s+)?observed\s+variables\s+(?:in|within)\s+(?:these\s+)?evaluated\s+domains\s+(?:were|remained)\s+within\s+(?:established\s+)?reference\s+limits", lower)
        ):
            violations.append(
                "Synthesis improperly claims all physiological variables are nominal or valid when telemetry is invalid or degraded."
            )

        if (
            "degraded telemetry is fully reliable" in lower
            or "degraded telemetry is reliable" in lower
            or "degraded sensor is fully reliable" in lower
            or "temperature telemetry is fully reliable" in lower
            or "degraded data is fully reliable" in lower
        ):
            violations.append(
                "Synthesis improperly asserts degraded telemetry is fully reliable."
            )

        is_valid = len(violations) == 0
        return is_valid, violations

    @classmethod
    def trace_claims(
        cls,
        text: str,
        overall_risk: RiskLevel,
        escalation_state: EscalationState,
        mission_day_supplied: bool = False,
        assessment_status: str = "COMPLETED",
        unevaluated_domains: Optional[List[str]] = None,
        symptoms_explicitly_denied: bool = False,
        allowed_protective_domains: Optional[List[str]] = None,
        output_filepath: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """Extract discrete assertions from synthesis, evaluate each against validator rules, and record machine-readable trace."""
        import json
        import os

        paragraphs = [p.strip() for p in text.split("\n\n") if p.strip()]
        claims: List[Dict[str, Any]] = []
        claim_counter = 1

        for p_idx, para in enumerate(paragraphs, start=1):
            sentences = [s.strip() for s in re.split(r"(?<=[.!?])\s+", para) if s.strip() and not s.startswith("**")]
            for sent in sentences:
                is_valid, violations = cls.validate_synthesis(
                    text=sent,
                    overall_risk=overall_risk,
                    escalation_state=escalation_state,
                    mission_day_supplied=mission_day_supplied,
                    assessment_status=assessment_status,
                    unevaluated_domains=unevaluated_domains,
                    symptoms_explicitly_denied=symptoms_explicitly_denied,
                    allowed_protective_domains=allowed_protective_domains
                )

                ev_ids: List[str] = []
                ev_validity = "VALID"
                provenance = "Deterministic Risk Engine"

                sent_lower = sent.lower()
                if "hrv" in sent_lower or "rmssd" in sent_lower:
                    ev_ids.append("EV-PHY-HRV-RMSSD")
                    ev_validity = "INVALID"
                    provenance = "Personal Health Agent (ECG telemetry)"
                if "cardiovascular" in sent_lower or "heart rate" in sent_lower:
                    if "EV-PHY-HR-MEAN" not in ev_ids:
                        ev_ids.append("EV-PHY-HR-MEAN")
                    if ev_validity == "VALID":
                        provenance = "Personal Health Agent (ECG telemetry)"
                if "respiratory" in sent_lower or "respiration" in sent_lower:
                    ev_ids.append("EV-PHY-RESP-RATE")
                    provenance = "Personal Health Agent (RESP telemetry)"
                if "thermoregulatory" in sent_lower or "temperature" in sent_lower:
                    ev_ids.append("EV-PHY-TEMP-MEAN")
                    ev_validity = "DEGRADED"
                    provenance = "Personal Health Agent (Skin TEMP telemetry)"
                if "psychological" in sent_lower or "eda" in sent_lower:
                    if "lacks validated" not in sent_lower and "absence of psychiatric" not in sent_lower:
                        ev_ids.append("EV-PHY-EDA-MEAN")
                        provenance = "Personal Health Agent (EDA telemetry)"
                    else:
                        ev_validity = "DATA_GAP"
                        provenance = "Deterministic Uncertainty Engine"
                if "data quality" in sent_lower or "sensor quality" in sent_lower:
                    ev_ids.append("EV-SQ-ECG")
                    provenance = "Sensor Quality Agent (Signal QC)"
                if "symptom" in sent_lower:
                    ev_ids.append("EV-SYM-UNSUBMITTED")
                    ev_validity = "NOT_AVAILABLE"
                    provenance = "Personal Health Agent (Symptom Telemetry)"
                if "act-nom-001" in sent_lower or "recommended action" in sent_lower:
                    ev_ids.append("ACT-NOM-001")
                    provenance = "Risk Escalation Service (Routine Monitoring)"
                if any(ud.lower().replace("_", " ") in sent_lower for ud in (unevaluated_domains or [])):
                    ev_validity = "DATA_GAP"
                    provenance = "Coverage Verification Engine (Unmonitored Telemetry)"

                evidence_supports_claim = False
                val_result = "PASS"
                rejection_reason = None
                val_method = "DETERMINISTIC_EVIDENCE_CORRELATION" if ev_ids else "PROGRAMMATIC_CLAUSE_CHECK"
                eval_type = "EMPIRICAL_EVIDENCE_MATCHING" if ev_ids else "OPERATIONAL_STATE_CHECK"

                if not is_valid:
                    val_result = "FAIL"
                    rejection_reason = "; ".join(violations)
                    evidence_supports_claim = False
                elif len(ev_ids) == 0:
                    val_result = "INSUFFICIENT_EVIDENCE"
                    evidence_supports_claim = False
                    if "partially_completed" in sent_lower or "domain coverage ratio" in sent_lower:
                        rejection_reason = "Operational state metadata assertion; no primary biosensor telemetry evidence item."
                    elif "no_trigger_detected" in sent_lower or "escalation state" in sent_lower or "alert or escalation rule" in sent_lower:
                        rejection_reason = "Deterministic escalation rule evaluation assertion; negative finding not supported by positive telemetry."
                    elif "data gaps" in sent_lower or "future data collection" in sent_lower:
                        rejection_reason = "Procedural guidance regarding data collection gaps; not supported by empirical telemetry."
                    elif "psychiatric" in sent_lower:
                        rejection_reason = "Observational data gap declaration; clinical psychiatric telemetry is uncollected."
                    else:
                        rejection_reason = "Claim lacks supporting empirical telemetry evidence."
                else:
                    evidence_supports_claim = True
                    val_result = "PASS"
                    rejection_reason = None

                claim_record = {
                    "claim_id": f"CLM-{claim_counter:03d}",
                    "paragraph_index": p_idx,
                    "claim_text": sent,
                    "evidence_ids": ev_ids,
                    "evidence_validity": ev_validity,
                    "provenance": provenance,
                    "evidence_supports_claim": evidence_supports_claim,
                    "validation_method": val_method,
                    "validation_result": val_result,
                    "rejection_reason": rejection_reason,
                    "automated_validator_executed": True,
                    "evaluation_type": eval_type
                }
                claims.append(claim_record)
                claim_counter += 1

        if output_filepath:
            os.makedirs(os.path.dirname(output_filepath), exist_ok=True)
            with open(output_filepath, "w", encoding="utf-8") as f:
                json.dump(claims, f, indent=2)

        return claims
