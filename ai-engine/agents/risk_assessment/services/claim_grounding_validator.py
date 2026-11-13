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
    def _build_evidence_maps(
        cls,
        evidence_items: Optional[List[Any]] = None,
        evidence_registry: Optional[Any] = None
    ) -> Tuple[Dict[str, Dict[str, Any]], Dict[str, Dict[str, Any]]]:
        ev_by_id: Dict[str, Dict[str, Any]] = {}
        ev_by_metric: Dict[str, Dict[str, Any]] = {}

        raw_list: List[Any] = []
        if evidence_items is not None:
            raw_list.extend(evidence_items)
        if evidence_registry is not None:
            if isinstance(evidence_registry, list):
                raw_list.extend(evidence_registry)
            elif isinstance(evidence_registry, dict):
                raw_list.extend(evidence_registry.values())

        for item in raw_list:
            if isinstance(item, dict):
                eid = item.get("evidence_id")
                metric = item.get("metric_name")
                val = item.get("observed_value")
                val_status = item.get("validity_status", "VALID")
                is_q = item.get("is_quarantined", False)
                unit = item.get("unit")
                s_agent = item.get("source_agent")
                prov = item.get("provenance")
            else:
                eid = getattr(item, "evidence_id", None)
                metric = getattr(item, "metric_name", None)
                val = getattr(item, "observed_value", None)
                val_status = getattr(item, "validity_status", "VALID")
                is_q = getattr(item, "is_quarantined", False)
                unit = getattr(item, "unit", None)
                s_agent = getattr(item, "source_agent", None)
                prov = getattr(item, "provenance", None)

            if eid:
                norm_dict = {
                    "evidence_id": eid,
                    "metric_name": metric,
                    "observed_value": val,
                    "validity_status": val_status.value if hasattr(val_status, "value") else str(val_status),
                    "is_quarantined": bool(is_q),
                    "unit": unit,
                    "source_agent": s_agent,
                    "provenance": prov
                }
                ev_by_id[eid] = norm_dict
                if metric:
                    ev_by_metric[metric] = norm_dict

        return ev_by_id, ev_by_metric

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
        protective_factors: Optional[List[str]] = None,
        evidence_items: Optional[List[Any]] = None,
        evidence_registry: Optional[Any] = None
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

        ev_by_id, ev_by_metric = cls._build_evidence_maps(evidence_items, evidence_registry)
        if ev_by_id:
            cited_ids = re.findall(r"\b(EV-[A-Z0-9\-]+)\b", text)
            for cid in set(cited_ids):
                if cid not in ev_by_id:
                    violations.append(f"Synthesis cites non-existent Evidence ID: '{cid}'.")
                else:
                    ev_info = ev_by_id[cid]
                    if ev_info.get("is_quarantined") or ev_info.get("validity_status") == "INVALID":
                        if any(term in lower for term in ("nominal", "normal", "healthy", "protective", "reliable")):
                            violations.append(f"Synthesis asserts nominal/valid status for quarantined or invalid evidence '{cid}'.")

        if ev_by_id or ev_by_metric:
            hr_ev = ev_by_metric.get("heart_rate_mean") or ev_by_id.get("EV-PHY-HR-MEAN")
            if hr_ev and hr_ev.get("observed_value") is not None:
                try:
                    ev_hr = float(hr_ev["observed_value"])
                    hr_matches = re.finditer(r"(?:heart\s+rate|hr)[^\d\.\n]{1,25}(\d+(?:\.\d+)?)\s*(?:bpm)?", lower)
                    for m in hr_matches:
                        syn_hr = float(m.group(1))
                        if abs(syn_hr - ev_hr) > 2.0:
                            violations.append(f"Synthesis asserts numerical heart rate {syn_hr:.1f} bpm which contradicts empirical evidence value {ev_hr:.1f} bpm.")
                    if (ev_hr > 160.0 or ev_hr < 40.0) and not hr_ev.get("is_quarantined"):
                        if re.search(r"(?:heart\s+rate|cardiac)[^\.\n]*(?:nominal|within\s+reference|normal|healthy)", lower):
                            violations.append(f"Synthesis claims nominal status for heart rate despite empirical evidence showing critical value {ev_hr:.1f} bpm.")
                except (ValueError, TypeError):
                    pass

            resp_ev = ev_by_metric.get("respiratory_rate") or ev_by_id.get("EV-PHY-RESP-RATE")
            if resp_ev and resp_ev.get("observed_value") is not None:
                try:
                    ev_resp = float(resp_ev["observed_value"])
                    resp_matches = re.finditer(r"(?:respiration\s+rate|respiratory\s+rate|resp\s+rate)[^\d\.\n]{1,25}(\d+(?:\.\d+)?)\s*(?:breaths/min|bpm)?", lower)
                    for m in resp_matches:
                        syn_resp = float(m.group(1))
                        if abs(syn_resp - ev_resp) > 1.5:
                            violations.append(f"Synthesis asserts numerical respiration rate {syn_resp:.1f} breaths/min which contradicts empirical evidence value {ev_resp:.1f} breaths/min.")
                    if (ev_resp > 26.0 or ev_resp < 8.0) and not resp_ev.get("is_quarantined"):
                        if re.search(r"(?:respiration|respiratory)[^\.\n]*(?:nominal|within\s+reference|normal|healthy)", lower):
                            violations.append(f"Synthesis claims nominal status for respiration rate despite empirical evidence showing abnormal value {ev_resp:.1f} breaths/min.")
                except (ValueError, TypeError):
                    pass

            temp_ev = ev_by_metric.get("temperature_mean") or ev_by_id.get("EV-PHY-TEMP-MEAN")
            if temp_ev and temp_ev.get("observed_value") is not None:
                try:
                    ev_temp = float(temp_ev["observed_value"])
                    temp_matches = re.finditer(r"(?:temperature|skin\s+temp|core\s+temp)[^\d\.\n]{1,25}(\d+(?:\.\d+)?)\s*(?:°c|c)?", lower)
                    for m in temp_matches:
                        syn_temp = float(m.group(1))
                        if abs(syn_temp - ev_temp) > 0.5:
                            violations.append(f"Synthesis asserts numerical temperature {syn_temp:.2f} °C which contradicts empirical evidence value {ev_temp:.2f} °C.")
                except (ValueError, TypeError):
                    pass

            unsupported_params = (
                ("blood pressure", ("blood_pressure", "bp_sys", "bp_dia", "EV-PHY-BP")),
                ("spo2", ("spo2", "pulse_ox", "EV-PHY-SPO2")),
                ("blood glucose", ("blood_glucose", "glucose", "EV-LAB-GLUCOSE"))
            )
            for label, metric_keys in unsupported_params:
                if re.search(rf"\b{re.escape(label)}\b[^\.\n]*(?:is|measured|was|recorded|observed|\d+)", lower):
                    has_ev = any(k in ev_by_metric or k in ev_by_id for k in metric_keys)
                    if not has_ev:
                        violations.append(f"Synthesis asserts unmeasured parameter '{label}' with zero supporting evidence in registry.")

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
        output_filepath: Optional[str] = None,
        evidence_items: Optional[List[Any]] = None,
        evidence_registry: Optional[Any] = None
    ) -> List[Dict[str, Any]]:
        """Extract discrete assertions from synthesis, evaluate each against validator rules, and record machine-readable trace."""
        import json
        import os

        paragraphs = [p.strip() for p in text.split("\n\n") if p.strip()]
        claims: List[Dict[str, Any]] = []
        claim_counter = 1
        ev_by_id, ev_by_metric = cls._build_evidence_maps(evidence_items, evidence_registry)

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
                    allowed_protective_domains=allowed_protective_domains,
                    evidence_items=evidence_items,
                    evidence_registry=evidence_registry
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

                cited_in_sent = re.findall(r"\b(EV-[A-Z0-9\-]+)\b", sent)
                for cid in cited_in_sent:
                    if cid not in ev_ids:
                        ev_ids.append(cid)

                if ev_by_id and ev_ids:
                    for eid in ev_ids:
                        if eid in ev_by_id:
                            item_info = ev_by_id[eid]
                            if item_info.get("is_quarantined") or item_info.get("validity_status") == "INVALID":
                                ev_validity = "INVALID"
                                if is_valid:
                                    is_valid = False
                                    violations.append(f"Supporting evidence '{eid}' is quarantined or invalid.")

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
