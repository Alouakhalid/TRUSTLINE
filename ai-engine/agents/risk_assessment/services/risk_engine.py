"""Deterministic risk assessment engine evaluating normalized evidence against registered rules."""
import re
from typing import Dict, List, Optional, Tuple, Any, NamedTuple
from ..schemas.evidence import (
    RiskDomain,
    EvidenceSourceType,
    EvidenceValidity,
    NormalizedEvidenceItem
)
from ..schemas.risk_rules import (
    RiskLevel,
    RiskConfidence,
    TriggeredRuleDetail,
    NonTriggeredRuleDetail
)
from ..schemas.risk_output import (
    IdentifiedConcern,
    RiskDomainAssessment,
    EvidenceSummaryItem,
    AssessmentCoverage,
    ProtectiveFactorItem
)
from .rule_registry import RuleRegistry

class RiskEvaluationResult(NamedTuple):
    """Structured container holding comprehensive risk engine evaluation outputs."""
    overall_risk: RiskLevel
    overall_confidence: RiskConfidence
    domain_assessments: List[RiskDomainAssessment]
    concerns: List[IdentifiedConcern]
    triggered_rules: List[TriggeredRuleDetail]
    non_triggered_rules: List[NonTriggeredRuleDetail]
    evidence_summary: List[EvidenceSummaryItem]
    uncertainties: List[str]
    missing_info: List[str]
    protective_factors: List[str]
    evaluated_domains_risk: RiskLevel
    assessment_status: str
    coverage: AssessmentCoverage
    protective_factor_details: List[ProtectiveFactorItem]
    nominal_observations: List[str] = []
    nominal_observation_details: List[ProtectiveFactorItem] = []

class RiskEngine:
    """Evaluates evidence deterministically across physiological and operational risk domains."""

    SEVERITY_ORDER: Dict[RiskLevel, int] = {
        RiskLevel.CRITICAL: 5,
        RiskLevel.HIGH: 4,
        RiskLevel.MODERATE: 3,
        RiskLevel.LOW: 2,
        RiskLevel.INSUFFICIENT_DATA: 1,
        RiskLevel.UNKNOWN: 0
    }

    DOMAIN_EVIDENCE_REQUIREMENTS: Dict[RiskDomain, str] = {
        RiskDomain.CARDIOVASCULAR: "Heart rate (ECG/BVP), HRV (RMSSD/SDNN), blood pressure, or cardiovascular symptoms",
        RiskDomain.RESPIRATORY: "Respiration rate, RIP breathing waveform, cabin atmospheric CO2/O2, or dyspnea symptoms",
        RiskDomain.NEUROLOGICAL: "Neurological/cognitive assessment, EEG telemetry, or neuro-vestibular symptoms",
        RiskDomain.SLEEP_AND_FATIGUE: "Sleep duration telemetry/log (actual_sleep_hours), circadian markers, or actigraphy",
        RiskDomain.PSYCHOLOGICAL_AND_COGNITIVE: "Electrodermal activity (EDA), validated cognitive performance tests, or acute stress indicators",
        RiskDomain.THERMOREGULATORY: "Core body temperature or continuous skin temperature telemetry",
        RiskDomain.HYDRATION_AND_FLUID_BALANCE: "Fluid intake/output logs, continuous body mass tracking, or hydration biomarkers",
        RiskDomain.MUSCULOSKELETAL: "Electromyography (EMG), daily exercise logs, or musculoskeletal complaint telemetry",
        RiskDomain.GENERAL_PHYSIOLOGICAL: "Multisystem lab panels, metabolic indicators, or general medical findings",
        RiskDomain.DATA_QUALITY_RELATED: "Sensor Quality Agent report covering active physiological sensors"
    }

    def __init__(self, registry: Optional[RuleRegistry] = None):
        self.registry = registry or RuleRegistry()

    def evaluate_risks(
        self,
        evidence_items: List[NormalizedEvidenceItem]
    ) -> RiskEvaluationResult:
        """Execute deterministic evaluation returning domain assessments, coverage, concerns, and rule audits."""
        ev_by_metric: Dict[str, NormalizedEvidenceItem] = {e.metric_name: e for e in evidence_items}
        ev_by_domain: Dict[RiskDomain, List[NormalizedEvidenceItem]] = {}
        for e in evidence_items:
            ev_by_domain.setdefault(e.domain, []).append(e)

        triggered_rules: List[TriggeredRuleDetail] = []
        non_triggered_rules: List[NonTriggeredRuleDetail] = []

        for rule in self.registry.get_all_rules():
            is_trig, trig_detail, non_trig_detail = self.registry.evaluate_rule(rule.rule_id, ev_by_metric)
            if is_trig and trig_detail:
                triggered_rules.append(trig_detail)
            elif non_trig_detail:
                non_triggered_rules.append(non_trig_detail)

        domain_assessments: List[RiskDomainAssessment] = []
        concerns: List[IdentifiedConcern] = []
        uncertainties: List[str] = []
        missing_info: List[str] = []
        protective_factor_details: List[ProtectiveFactorItem] = []
        nominal_observation_details: List[ProtectiveFactorItem] = []

        evaluated_domains: List[RiskDomain] = []
        unevaluated_domains: List[RiskDomain] = []
        partially_evaluated_domains: List[RiskDomain] = []
        unavailable_domain_reasons: Dict[str, str] = {}

        all_domains = list(RiskDomain)
        for dom in all_domains:
            dom_evidence = ev_by_domain.get(dom, [])
            dom_triggered = [r for r in triggered_rules if r.domain == dom]
            dom_eligible_evidence = [
                e for e in dom_evidence
                if e.validity_status in (EvidenceValidity.VALID, EvidenceValidity.DEGRADED)
                and getattr(e, "is_eligible_for_risk", True)
            ]

            if not dom_evidence:
                unevaluated_domains.append(dom)
                req_text = self.DOMAIN_EVIDENCE_REQUIREMENTS.get(dom, "Domain telemetry")
                reason_text = f"No observational telemetry or validated records available. Required evidence: {req_text}."
                unavailable_domain_reasons[dom.value] = reason_text

                domain_assessments.append(
                    RiskDomainAssessment(
                        domain=dom,
                        assessment_status="NOT_EVALUATED",
                        risk_level=RiskLevel.UNKNOWN,
                        confidence=RiskConfidence.UNDETERMINED,
                        supporting_evidence_ids=[],
                        triggered_rule_ids=[],
                        limitations=[f"No telemetry or subjective observations provided for {dom.value} ({req_text})."],
                        explanation=f"Domain {dom.value} was not evaluated due to absence of domain telemetry.",
                        requires_human_review=False
                    )
                )
                uncertainties.append(f"Domain {dom.value} is unevaluated: Telemetry unavailable for {req_text}.")
                missing_info.append(f"Observational evidence for {dom.value} ({req_text}).")
                continue

            has_invalid_primary = any(e.validity_status == EvidenceValidity.INVALID for e in dom_evidence)
            all_invalid = all(e.validity_status == EvidenceValidity.INVALID for e in dom_evidence)

            if all_invalid and not dom_triggered:
                partially_evaluated_domains.append(dom)
                domain_assessments.append(
                    RiskDomainAssessment(
                        domain=dom,
                        assessment_status="INSUFFICIENT_DATA",
                        risk_level=RiskLevel.INSUFFICIENT_DATA,
                        confidence=RiskConfidence.LOW,
                        supporting_evidence_ids=[e.evidence_id for e in dom_evidence],
                        triggered_rule_ids=[],
                        limitations=["All observational evidence in this domain failed sensor quality validation."],
                        explanation=f"Telemetry for {dom.value} is marked INVALID; deterministic safety rules cannot be verified.",
                        requires_human_review=True
                    )
                )
                uncertainties.append(f"Domain {dom.value} telemetry is INVALID; physiological status remains indeterminate.")
                continue

            if not dom_eligible_evidence and not dom_triggered:
                unevaluated_domains.append(dom)
                req_text = self.DOMAIN_EVIDENCE_REQUIREMENTS.get(dom, "Domain telemetry")
                reason_text = (
                    "No eligible observational evidence or confirmed symptom reports submitted. Unsubmitted symptoms represent unknown symptom status."
                    if dom == RiskDomain.GENERAL_PHYSIOLOGICAL
                    else f"No eligible observational telemetry or validated records available. Required evidence: {req_text}."
                )
                unavailable_domain_reasons[dom.value] = reason_text
                domain_assessments.append(
                    RiskDomainAssessment(
                        domain=dom,
                        assessment_status="NOT_EVALUATED",
                        risk_level=RiskLevel.UNKNOWN,
                        confidence=RiskConfidence.UNDETERMINED,
                        supporting_evidence_ids=[],
                        triggered_rule_ids=[],
                        limitations=[reason_text],
                        explanation=f"Domain {dom.value} was not evaluated due to absence of eligible domain telemetry or confirmed symptom assessments.",
                        requires_human_review=False
                    )
                )
                uncertainties.append(f"Domain {dom.value} is unevaluated: {reason_text}")
                missing_info.append(f"Observational evidence for {dom.value} ({req_text}).")
                continue

            evaluated_domains.append(dom)

            if dom_triggered:
                highest_dom_risk = max(
                    (r.risk_level for r in dom_triggered),
                    key=lambda rk: self.SEVERITY_ORDER[rk]
                )
                dom_conf = RiskConfidence.HIGH
                if any(e.validity_status in (EvidenceValidity.DEGRADED, EvidenceValidity.UNCERTAIN) for e in dom_evidence):
                    dom_conf = RiskConfidence.LOW
                    uncertainties.append(f"Telemetry in domain {dom.value} is DEGRADED; evidential confidence attenuated to LOW.")
                if has_invalid_primary:
                    dom_conf = RiskConfidence.LOW
                    uncertainties.append(f"Primary telemetry in domain {dom.value} is INVALID; evidential confidence attenuated to LOW.")

                rule_ids = [r.rule_id for r in dom_triggered]
                ev_ids = list(set(ev_id for r in dom_triggered for ev_id in r.supporting_evidence_ids))

                domain_assessments.append(
                    RiskDomainAssessment(
                        domain=dom,
                        assessment_status="EVALUATED",
                        risk_level=highest_dom_risk,
                        confidence=dom_conf,
                        supporting_evidence_ids=ev_ids,
                        triggered_rule_ids=rule_ids,
                        limitations=[r.rationale for r in dom_triggered],
                        explanation=(
                            f"Domain {dom.value} evaluated as {highest_dom_risk.value} based on "
                            f"{len(dom_triggered)} triggered deterministic rule(s): {', '.join(rule_ids)}."
                        ),
                        requires_human_review=(highest_dom_risk in (RiskLevel.HIGH, RiskLevel.CRITICAL) or dom_conf == RiskConfidence.LOW)
                    )
                )

                for r in dom_triggered:
                    concerns.append(
                        IdentifiedConcern(
                            concern_id=f"CONCERN-{dom.value[:4]}-{r.rule_id}",
                            domain=dom,
                            severity=r.risk_level,
                            title=r.rule_name,
                            description=r.rationale,
                            supporting_evidence_ids=r.supporting_evidence_ids,
                            rule_id=r.rule_id,
                            uncertainty_note="Evidence degraded" if dom_conf == RiskConfidence.LOW else None
                        )
                    )
            else:
                dom_conf = RiskConfidence.HIGH
                dom_limitations: List[str] = []

                if any(e.validity_status in (EvidenceValidity.DEGRADED, EvidenceValidity.UNCERTAIN) for e in dom_evidence):
                    dom_conf = RiskConfidence.MODERATE
                    uncertainties.append(f"Telemetry in domain {dom.value} is DEGRADED; evidential confidence attenuated to MODERATE.")

                if dom == RiskDomain.CARDIOVASCULAR:
                    hrv_ev = ev_by_metric.get("hrv_rmssd")
                    has_invalid_hrv = bool(
                        hrv_ev and (hrv_ev.validity_status == EvidenceValidity.INVALID or not getattr(hrv_ev, "is_eligible_for_risk", True))
                    )
                    if has_invalid_hrv:
                        dom_conf = RiskConfidence.MODERATE
                        dom_limitations.append(
                            "Cardiac autonomic HRV evidence (RMSSD) is INVALID (ZERO_VARIABILITY artifact); autonomic regulation cannot be confirmed from HRV."
                        )
                        uncertainties.append(
                            "Cardiovascular HRV RMSSD is INVALID (ZERO_VARIABILITY); autonomic cardiac regulation confidence attenuated to MODERATE."
                        )

                elif dom == RiskDomain.PSYCHOLOGICAL_AND_COGNITIVE:
                    has_experimental_or_eda = any(
                        getattr(e, "evidence_classification", "") == "EXPERIMENTAL_CONTEXT"
                        or e.source_type == EvidenceSourceType.EXPERIMENTAL_ML_CLASSIFIER
                        or e.metric_name == "eda_mean"
                        for e in dom_evidence
                    )
                    if has_experimental_or_eda:
                        dom_conf = RiskConfidence.MODERATE
                        dom_limitations.append(
                            "Psychological assessment limited to peripheral autonomic electrodermal activity (EDA) and experimental laboratory ML benchmark; validated clinical psychiatric and cognitive testing is unavailable."
                        )
                        uncertainties.append(
                            "Psychological domain lacks validated clinical psychiatric and cognitive testing; evidential confidence capped at MODERATE."
                        )

                elif dom == RiskDomain.THERMOREGULATORY:
                    temp_ev = ev_by_metric.get("temperature_mean")
                    meas_type = temp_ev.raw_context.get("measurement_type") if (temp_ev and temp_ev.raw_context) else None
                    if meas_type == "SKIN_SURFACE_TEMPERATURE" or (temp_ev and temp_ev.validity_status == EvidenceValidity.DEGRADED):
                        dom_conf = RiskConfidence.MODERATE
                        dom_limitations.append(
                            f"Thermoregulatory telemetry reflects peripheral skin surface temperature ({float(temp_ev.observed_value):.2f} °C) with {temp_ev.quality_status or 'ACCEPTABLE_WITH_WARNING'} quality; core body temperature is not directly monitored."
                        )
                        uncertainties.append(
                            "Thermoregulatory telemetry reflects peripheral skin temperature, not core body temperature."
                        )

                dom_sup_ids = [e.evidence_id for e in dom_eligible_evidence]

                domain_assessments.append(
                    RiskDomainAssessment(
                        domain=dom,
                        assessment_status="EVALUATED",
                        risk_level=RiskLevel.LOW,
                        confidence=dom_conf,
                        supporting_evidence_ids=dom_sup_ids,
                        triggered_rule_ids=[],
                        limitations=dom_limitations,
                        explanation=f"All observed variables in {dom.value} were within established reference limits; no rule triggered.",
                        requires_human_review=False
                    )
                )

                if dom == RiskDomain.CARDIOVASCULAR:
                    hr_ev = ev_by_metric.get("heart_rate_mean")
                    hrv_ev = ev_by_metric.get("hrv_rmssd")
                    has_invalid_hrv = bool(
                        hrv_ev and (hrv_ev.validity_status == EvidenceValidity.INVALID or not getattr(hrv_ev, "is_eligible_for_risk", True))
                    )
                    if hr_ev and hr_ev.validity_status == EvidenceValidity.VALID and 50.0 <= float(hr_ev.observed_value) <= 100.0:
                        if not has_invalid_hrv:
                            nominal_observation_details.append(
                                ProtectiveFactorItem(
                                    factor_id="OBS-CARDIO-WNL-01",
                                    domain=dom,
                                    source_agent=hr_ev.source_agent,
                                    supporting_evidence_ids=[hr_ev.evidence_id],
                                    validity_status=EvidenceValidity.VALID,
                                    applicable_criterion="Clinical Physiology Reference: Adult Heart Rate (50-100 bpm; verifiable source: Harrison's Principles of Internal Medicine / Guyton & Hall; resting state unconfirmed in telemetry); In-Mission Medical Care Vital Signs Capability per NASA-STD-3001 Volume 1 Revision C [V1 3004] (numerical range is a clinical reference, not a direct NASA standard threshold requirement)",
                                    explanation=f"Heart rate ({float(hr_ev.observed_value):.1f} bpm) verified nominal within standard clinical reference limits (50-100 bpm; verifiable source: Harrison's Principles of Internal Medicine; resting conditions unconfirmed in session) with valid ECG.",
                                    factor_type="NOMINAL_OBSERVATION"
                                )
                            )
                elif dom == RiskDomain.RESPIRATORY:
                    resp_ev = ev_by_metric.get("respiratory_rate")
                    if resp_ev and resp_ev.validity_status == EvidenceValidity.VALID and 10.0 <= float(resp_ev.observed_value) <= 20.0:
                        nominal_observation_details.append(
                            ProtectiveFactorItem(
                                factor_id="OBS-RESP-WNL-01",
                                domain=dom,
                                source_agent=resp_ev.source_agent,
                                supporting_evidence_ids=[resp_ev.evidence_id],
                                validity_status=EvidenceValidity.VALID,
                                applicable_criterion="Clinical Physiology Reference: Adult Eupnea (10-20 breaths/min; verifiable source: Harrison's Principles of Internal Medicine / Bates' Guide to Physical Examination; resting state unconfirmed in telemetry); In-Mission Medical Care Vital Signs Capability per NASA-STD-3001 Volume 1 Revision C [V1 3004] (numerical range is a clinical reference, not a direct NASA standard threshold requirement)",
                                explanation=f"Respiration rate ({float(resp_ev.observed_value):.1f} breaths/min) verified nominal within standard clinical reference limits (10-20 breaths/min; verifiable source: Harrison's Principles of Internal Medicine; resting conditions unconfirmed in session; in-mission monitoring capability per NASA-STD-3001-VOL-1 Rev C [V1 3004]).",
                                factor_type="NOMINAL_OBSERVATION"
                            )
                        )
                elif dom == RiskDomain.THERMOREGULATORY:
                    temp_ev = ev_by_metric.get("temperature_mean")
                    meas_type = temp_ev.raw_context.get("measurement_type") if (temp_ev and temp_ev.raw_context) else None
                    if meas_type != "SKIN_SURFACE_TEMPERATURE" and temp_ev and temp_ev.validity_status == EvidenceValidity.VALID and 36.5 <= float(temp_ev.observed_value) <= 37.5:
                        nominal_observation_details.append(
                            ProtectiveFactorItem(
                                factor_id="OBS-THERM-WNL-01",
                                domain=dom,
                                source_agent=temp_ev.source_agent,
                                supporting_evidence_ids=[temp_ev.evidence_id],
                                validity_status=EvidenceValidity.VALID,
                                applicable_criterion="Clinical Physiology Reference: Adult Core Body Temperature (36.5-37.5 °C; verifiable source: Guyton & Hall Medical Physiology); In-Mission Medical Care Vital Signs Capability per NASA-STD-3001 Volume 1 Revision C [V1 3004] (numerical range is a clinical reference, not a direct NASA standard threshold requirement)",
                                explanation=f"Body temperature ({float(temp_ev.observed_value):.2f} °C) verified nominal within standard clinical thermoregulatory limits (36.5-37.5 °C; verifiable source: Guyton & Hall).",
                                factor_type="NOMINAL_OBSERVATION"
                            )
                        )

        sq_items = [e for e in evidence_items if e.source_type.value == "sensor_quality"]
        if sq_items:
            sq_all_valid = all(e.validity_status == EvidenceValidity.VALID for e in sq_items)
            no_sq_rule_triggered = not any(r.rule_id == "RR-DATA-SENSOR-CRITICAL-FAIL" for r in triggered_rules)
            if sq_all_valid and no_sq_rule_triggered:
                protective_factor_details.append(
                    ProtectiveFactorItem(
                        factor_id="PROT-DATA-QUALITY-01",
                        domain=RiskDomain.DATA_QUALITY_RELATED,
                        source_agent="sensor_quality_agent",
                        supporting_evidence_ids=[e.evidence_id for e in sq_items],
                        validity_status=EvidenceValidity.VALID,
                        applicable_criterion="TRUSTLINE-SQA-SYS-2026-V1.0 Signal Quality Acceptance (Score >= 0.85, 0 Invalid Channels)",
                        explanation="All primary physiological sensor channels verified VALID with high signal integrity and zero signal loss.",
                        factor_type="PROTECTIVE_FACTOR"
                    )
                )
        else:
            uncertainties.append("Sensor Quality Agent report not provided; underlying sensor fidelity cannot be verified.")

        denied_sym = ev_by_metric.get("symptom_explicitly_denied")
        if denied_sym and denied_sym.validity_status == EvidenceValidity.VALID:
            protective_factor_details.append(
                ProtectiveFactorItem(
                    factor_id="PROT-SYM-DENIAL-01",
                    domain=RiskDomain.GENERAL_PHYSIOLOGICAL,
                    source_agent="personal_health_agent",
                    supporting_evidence_ids=[denied_sym.evidence_id],
                    validity_status=EvidenceValidity.VALID,
                    applicable_criterion="ISS-MEDOPS-SYMPTOM-PROTOCOL-V2.0 Confirmed Negative Symptom Questionnaire",
                    explanation="Astronaut explicitly confirmed absence of acute subjective symptoms during structured medical review.",
                    factor_type="PROTECTIVE_FACTOR"
                )
            )

        if ev_by_metric.get("symptom_status_unsubmitted"):
            uncertainties.append("Subjective symptoms were not submitted for this session; absence of reports does not establish clinical absence of symptoms.")

        if ev_by_metric.get("symptom_data_unavailable"):
            uncertainties.append("Subjective symptom assessment data is unavailable for this session.")

        total_domains_count = len(all_domains)
        coverage_ratio = round(len(evaluated_domains) / float(total_domains_count), 2)
        if coverage_ratio == 1.0:
            cov_status = "COMPLETE"
        elif coverage_ratio > 0.0:
            cov_status = "PARTIAL"
        else:
            cov_status = "INSUFFICIENT"

        coverage_report = AssessmentCoverage(
            total_domains=total_domains_count,
            evaluated_domains=evaluated_domains,
            unevaluated_domains=unevaluated_domains,
            partially_evaluated_domains=partially_evaluated_domains,
            domain_coverage_ratio=coverage_ratio,
            coverage_status=cov_status,
            unavailable_domain_reasons=unavailable_domain_reasons
        )

        if concerns:
            evaluated_domains_risk = max((c.severity for c in concerns), key=lambda rk: self.SEVERITY_ORDER[rk])
        elif evaluated_domains:
            evaluated_domains_risk = RiskLevel.LOW
        elif partially_evaluated_domains:
            evaluated_domains_risk = RiskLevel.INSUFFICIENT_DATA
        else:
            evaluated_domains_risk = RiskLevel.UNKNOWN

        if concerns:
            overall_risk = max((c.severity for c in concerns), key=lambda rk: self.SEVERITY_ORDER[rk])
        else:
            if coverage_ratio == 1.0:
                overall_risk = RiskLevel.LOW
            elif coverage_ratio > 0.0:
                overall_risk = RiskLevel.INSUFFICIENT_DATA
            else:
                overall_risk = RiskLevel.UNKNOWN

        if coverage_ratio == 1.0:
            assessment_status = "COMPLETED"
        elif coverage_ratio > 0.0:
            assessment_status = "PARTIALLY_COMPLETED"
        else:
            assessment_status = "INSUFFICIENT_DATA"

        evaluated_domain_objs = [d for d in domain_assessments if d.domain in evaluated_domains]
        if not evaluated_domain_objs:
            overall_confidence = RiskConfidence.UNDETERMINED
        elif any(d.confidence == RiskConfidence.LOW for d in evaluated_domain_objs):
            overall_confidence = RiskConfidence.LOW
        elif coverage_ratio < 1.0:
            overall_confidence = RiskConfidence.MODERATE
            uncertainties.append(
                f"Overall evidential confidence is capped at MODERATE due to partial assessment coverage ({len(evaluated_domains)}/10 domains evaluated)."
            )
        elif all(d.confidence == RiskConfidence.HIGH for d in evaluated_domain_objs):
            overall_confidence = RiskConfidence.HIGH
        else:
            overall_confidence = RiskConfidence.MODERATE

        evidence_summary: List[EvidenceSummaryItem] = []
        for e in evidence_items:
            evidence_summary.append(
                EvidenceSummaryItem(
                    evidence_id=e.evidence_id,
                    source_agent=e.source_agent,
                    domain=e.domain,
                    metric_name=e.metric_name,
                    observed_value_repr=f"{e.observed_value} {e.unit or ''}".strip(),
                    validity_status=e.validity_status,
                    quality_status=e.quality_status,
                    is_confirmed=e.is_confirmed,
                    relevance_summary=e.evidence_description,
                    evidence_classification=getattr(e, "evidence_classification", "CLINICAL_OBSERVATION"),
                    is_eligible_for_risk=getattr(e, "is_eligible_for_risk", True)
                )
            )

        canonical_uncertainties: List[str] = []
        seen_unc = set()
        for u in uncertainties:
            cleaned = u.strip().rstrip(".; ").strip()
            if not cleaned:
                continue
            norm_k = re.sub(r"\s+", " ", cleaned.lower())
            if norm_k not in seen_unc:
                seen_unc.add(norm_k)
                canonical_uncertainties.append(cleaned)

        protective_factors_strings = [p.explanation for p in protective_factor_details]
        nominal_observations_strings = [p.explanation for p in nominal_observation_details]

        return RiskEvaluationResult(
            overall_risk=overall_risk,
            overall_confidence=overall_confidence,
            domain_assessments=domain_assessments,
            concerns=concerns,
            triggered_rules=triggered_rules,
            non_triggered_rules=non_triggered_rules,
            evidence_summary=evidence_summary,
            uncertainties=canonical_uncertainties,
            missing_info=missing_info,
            protective_factors=protective_factors_strings,
            evaluated_domains_risk=evaluated_domains_risk,
            assessment_status=assessment_status,
            coverage=coverage_report,
            protective_factor_details=protective_factor_details,
            nominal_observations=nominal_observations_strings,
            nominal_observation_details=nominal_observation_details
        )
