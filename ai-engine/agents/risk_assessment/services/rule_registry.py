"""Traceable, evidence-based rule registry grounded in NASA-STD-3001 and ISS-MEDOPS protocols."""
from typing import Dict, List, Optional, Tuple, Callable
from ..schemas.evidence import RiskDomain, EvidenceValidity, NormalizedEvidenceItem
from ..schemas.risk_rules import (
    RiskLevel,
    EscalationState,
    EscalationDestination,
    RiskRule,
    TriggeredRuleDetail,
    NonTriggeredRuleDetail
)

class RuleRegistry:
    """Central repository of deterministic, authoritative aerospace clinical and operational rules."""

    def __init__(self):
        self._rules: Dict[str, RiskRule] = {}
        self._evaluators: Dict[str, Callable[[Dict[str, NormalizedEvidenceItem]], Tuple[bool, str, List[str]]]] = {}
        self._load_registered_rules()

    def get_rule(self, rule_id: str) -> Optional[RiskRule]:
        """Fetch rule metadata by identifier."""
        return self._rules.get(rule_id)

    def get_all_rules(self) -> List[RiskRule]:
        """Return all active registered rules."""
        return list(self._rules.values())

    def evaluate_rule(
        self,
        rule_id: str,
        evidence_dict: Dict[str, NormalizedEvidenceItem]
    ) -> Tuple[bool, Optional[TriggeredRuleDetail], Optional[NonTriggeredRuleDetail]]:
        """Evaluate a specific registered rule against normalized evidence."""
        rule = self._rules.get(rule_id)
        if not rule:
            return False, None, None

        eval_fn = self._evaluators.get(rule_id)
        if not eval_fn:
            return False, None, NonTriggeredRuleDetail(
                rule_id=rule.rule_id,
                rule_name=rule.rule_name,
                domain=rule.domain,
                evaluated_variables=rule.required_variables,
                evaluation_reason="Evaluator function not registered."
            )

        missing_vars = [v for v in rule.required_variables if v not in evidence_dict]
        if missing_vars:
            return False, None, NonTriggeredRuleDetail(
                rule_id=rule.rule_id,
                rule_name=rule.rule_name,
                domain=rule.domain,
                evaluated_variables=rule.required_variables,
                evaluation_reason=f"Missing required observational variables: {missing_vars}."
            )

        for s_cond in rule.required_quality_conditions:
            sensor_ev = evidence_dict.get(s_cond)
            if sensor_ev and sensor_ev.validity_status == EvidenceValidity.INVALID:
                return False, None, NonTriggeredRuleDetail(
                    rule_id=rule.rule_id,
                    rule_name=rule.rule_name,
                    domain=rule.domain,
                    evaluated_variables=rule.required_variables,
                    evaluation_reason=f"Required sensor quality condition '{s_cond}' is INVALID."
                )

        triggered, rationale, sup_ids = eval_fn(evidence_dict)
        if triggered:
            trig_detail = TriggeredRuleDetail(
                rule_id=rule.rule_id,
                rule_name=rule.rule_name,
                domain=rule.domain,
                risk_level=rule.risk_level,
                supporting_evidence_ids=sup_ids,
                rationale=rationale,
                suggested_escalation=rule.suggested_escalation,
                rule_source=rule.rule_source
            )
            return True, trig_detail, None
        else:
            non_trig = NonTriggeredRuleDetail(
                rule_id=rule.rule_id,
                rule_name=rule.rule_name,
                domain=rule.domain,
                evaluated_variables=rule.required_variables,
                evaluation_reason=rationale
            )
            return False, None, non_trig

    def _load_registered_rules(self):
        """Register all authoritative clinical, physiological, environmental, and quality rules."""

        rule_cp = RiskRule(
            rule_id="RR-EMERG-CHEST-PAIN",
            rule_name="Red-Line Trigger: Acute Severe Chest Pain Complaint",
            domain=RiskDomain.CARDIOVASCULAR,
            required_variables=["symptom_chest_pain"],
            threshold_condition="Explicit subjective report of chest pain or crushing sensation",
            risk_level=RiskLevel.CRITICAL,
            rule_source="ISS-MEDOPS-REDLINE-2025-V4.2",
            source_version="4.2",
            intended_scope="Emergency operational telemetry triage",
            limitations="Based on self-reported symptom statement without verified diagnostic ECG pathology",
            last_verification_date="2026-11-01",
            suggested_escalation=EscalationState.ESCALATION_REQUIRED,
            suggested_destination=EscalationDestination.EMERGENCY_MEDICAL_RESPONSE,
            recommended_action="Immediate Flight Surgeon alert, cease crew activity, prepare CMRS."
        )
        self._rules[rule_cp.rule_id] = rule_cp
        def _eval_cp(evs: Dict[str, NormalizedEvidenceItem]) -> Tuple[bool, str, List[str]]:
            ev = evs.get("symptom_chest_pain")
            if ev and ev.validity_status in (EvidenceValidity.VALID, EvidenceValidity.DEGRADED):
                return True, f"Subjective chest pain complaint registered: {ev.evidence_description}", [ev.evidence_id]
            return False, "No chest pain complaint reported.", []
        self._evaluators[rule_cp.rule_id] = _eval_cp

        rule_tachy = RiskRule(
            rule_id="RR-CARDIO-TACHY-EXTREME",
            rule_name="Red-Line Trigger: Extreme Resting Tachycardia",
            domain=RiskDomain.CARDIOVASCULAR,
            required_variables=["heart_rate_mean"],
            required_quality_conditions=["ECG_quality_score"],
            threshold_condition="Mean resting heart rate > 160.0 bpm with valid ECG telemetry",
            risk_level=RiskLevel.CRITICAL,
            rule_source="ISS-MEDOPS-REDLINE-2025-V4.2",
            source_version="4.2",
            intended_scope="Rest-state in-flight cardiac monitoring",
            limitations="Assumes resting activity state; strenuous exercise may produce physiological tachycardia",
            last_verification_date="2026-11-01",
            suggested_escalation=EscalationState.ESCALATION_REQUIRED,
            suggested_destination=EscalationDestination.EMERGENCY_MEDICAL_RESPONSE,
            recommended_action="Immediate Flight Surgeon notification, prompt seated/horizontal rest."
        )
        self._rules[rule_tachy.rule_id] = rule_tachy
        def _eval_tachy(evs: Dict[str, NormalizedEvidenceItem]) -> Tuple[bool, str, List[str]]:
            ev = evs.get("heart_rate_mean")
            if ev and ev.validity_status == EvidenceValidity.VALID and float(ev.observed_value) > 160.0:
                return True, f"Resting heart rate {ev.observed_value:.1f} bpm exceeds critical limit of 160.0 bpm.", [ev.evidence_id]
            val = ev.observed_value if ev else "N/A"
            return False, f"Resting heart rate ({val} bpm) does not exceed 160.0 bpm.", []
        self._evaluators[rule_tachy.rule_id] = _eval_tachy

        rule_brady = RiskRule(
            rule_id="RR-CARDIO-BRADY-EXTREME",
            rule_name="Red-Line Trigger: Extreme Resting Bradycardia",
            domain=RiskDomain.CARDIOVASCULAR,
            required_variables=["heart_rate_mean"],
            required_quality_conditions=["ECG_quality_score"],
            threshold_condition="Mean resting heart rate < 40.0 bpm with valid ECG telemetry",
            risk_level=RiskLevel.CRITICAL,
            rule_source="ISS-MEDOPS-REDLINE-2025-V4.2",
            source_version="4.2",
            intended_scope="Rest-state in-flight cardiac monitoring",
            limitations="Highly conditioned endurance astronauts may exhibit baseline resting rates near 45 bpm",
            last_verification_date="2026-11-01",
            suggested_escalation=EscalationState.ESCALATION_REQUIRED,
            suggested_destination=EscalationDestination.EMERGENCY_MEDICAL_RESPONSE,
            recommended_action="Notify Flight Surgeon immediately; evaluate for hemodynamic compromise or syncope."
        )
        self._rules[rule_brady.rule_id] = rule_brady
        def _eval_brady(evs: Dict[str, NormalizedEvidenceItem]) -> Tuple[bool, str, List[str]]:
            ev = evs.get("heart_rate_mean")
            if ev and ev.validity_status == EvidenceValidity.VALID and float(ev.observed_value) < 40.0:
                return True, f"Resting heart rate {ev.observed_value:.1f} bpm is below critical threshold of 40.0 bpm.", [ev.evidence_id]
            val = ev.observed_value if ev else "N/A"
            return False, f"Resting heart rate ({val} bpm) is not below 40.0 bpm.", []
        self._evaluators[rule_brady.rule_id] = _eval_brady

        rule_mod_tachy = RiskRule(
            rule_id="RR-CARDIO-TACHY-MODERATE",
            rule_name="Resting Moderate Tachycardia",
            domain=RiskDomain.CARDIOVASCULAR,
            required_variables=["heart_rate_mean"],
            required_quality_conditions=["ECG_quality_score"],
            threshold_condition="100.0 bpm < resting heart rate <= 160.0 bpm",
            risk_level=RiskLevel.MODERATE,
            rule_source="Clinical Cardiology (Harrison's Principles; in-mission vital signs monitoring capability per NASA-STD-3001-VOL-1 Rev C [V1 3004])",
            source_version="Revision C / Harrison's 21st Ed",
            intended_scope="Routine in-flight health monitoring",
            limitations="Transient elevations can result from emotional arousal or post-exercise cooldown",
            last_verification_date="2026-11-01",
            suggested_escalation=EscalationState.REVIEW_REQUIRED,
            suggested_destination=EscalationDestination.FLIGHT_SURGEON,
            recommended_action="Review astronaut physical context and verify repeat resting recording."
        )
        self._rules[rule_mod_tachy.rule_id] = rule_mod_tachy
        def _eval_mod_tachy(evs: Dict[str, NormalizedEvidenceItem]) -> Tuple[bool, str, List[str]]:
            ev = evs.get("heart_rate_mean")
            if ev and ev.validity_status == EvidenceValidity.VALID:
                hr = float(ev.observed_value)
                if 100.0 < hr <= 160.0:
                    return True, f"Resting heart rate {hr:.1f} bpm is moderately elevated (100-160 bpm).", [ev.evidence_id]
            return False, "Resting heart rate is not between 100 and 160 bpm.", []
        self._evaluators[rule_mod_tachy.rule_id] = _eval_mod_tachy

        rule_dyspnea = RiskRule(
            rule_id="RR-RESP-DYSPNEA-ALERT",
            rule_name="Respiratory Distress Complaint",
            domain=RiskDomain.RESPIRATORY,
            required_variables=["symptom_dyspnea"],
            threshold_condition="Reported severe shortness of breath or dyspnea",
            risk_level=RiskLevel.HIGH,
            rule_source="ISS-MEDOPS-REDLINE-2025-V4.2",
            source_version="4.2",
            intended_scope="Subjective symptom triage",
            limitations="Subjective report; requires correlation with cabin atmosphere and respiration sensor",
            last_verification_date="2026-11-01",
            suggested_escalation=EscalationState.ESCALATION_RECOMMENDED,
            suggested_destination=EscalationDestination.FLIGHT_SURGEON,
            recommended_action="Check cabin O2/CO2 levels, instruct astronaut to rest, evaluate respiratory rate."
        )
        self._rules[rule_dyspnea.rule_id] = rule_dyspnea
        def _eval_dyspnea(evs: Dict[str, NormalizedEvidenceItem]) -> Tuple[bool, str, List[str]]:
            ev = evs.get("symptom_dyspnea") or evs.get("symptom_shortness_of_breath")
            if ev and ev.validity_status in (EvidenceValidity.VALID, EvidenceValidity.DEGRADED):
                return True, f"Subjective respiratory distress reported: {ev.evidence_description}", [ev.evidence_id]
            return False, "No dyspnea reported.", []
        self._evaluators[rule_dyspnea.rule_id] = _eval_dyspnea

        rule_tachypnea = RiskRule(
            rule_id="RR-RESP-TACHYPNEA",
            rule_name="Resting Tachypnea",
            domain=RiskDomain.RESPIRATORY,
            required_variables=["respiratory_rate"],
            required_quality_conditions=["RESP_quality_score"],
            threshold_condition="Mean respiration rate > 26.0 breaths/min at rest with valid sensor",
            risk_level=RiskLevel.MODERATE,
            rule_source="Clinical Pulmonology (Bates' Guide; in-mission vital signs monitoring capability per NASA-STD-3001-VOL-1 Rev C [V1 3004])",
            source_version="Revision C / Bates 13th Ed",
            intended_scope="Telemetry rest analysis",
            limitations="Chest-band RIP motion artifacts may alter peak counting if sensor is degraded",
            last_verification_date="2026-11-01",
            suggested_escalation=EscalationState.REVIEW_REQUIRED,
            suggested_destination=EscalationDestination.FLIGHT_SURGEON,
            recommended_action="Inspect respiratory waveform and cross-check cabin atmospheric scrub status."
        )
        self._rules[rule_tachypnea.rule_id] = rule_tachypnea
        def _eval_tachypnea(evs: Dict[str, NormalizedEvidenceItem]) -> Tuple[bool, str, List[str]]:
            ev = evs.get("respiratory_rate")
            if ev and ev.validity_status == EvidenceValidity.VALID and float(ev.observed_value) > 26.0:
                return True, f"Resting respiration rate {ev.observed_value:.1f} breaths/min exceeds 26.0 bpm.", [ev.evidence_id]
            return False, "Respiration rate does not exceed 26.0 breaths/min.", []
        self._evaluators[rule_tachypnea.rule_id] = _eval_tachypnea

        rule_hyperthermia = RiskRule(
            rule_id="RR-THERM-HYPERTHERMIA",
            rule_name="Sustained Elevated Core Temperature",
            domain=RiskDomain.THERMOREGULATORY,
            required_variables=["temperature_mean"],
            required_quality_conditions=["TEMP_quality_score"],
            threshold_condition="Mean core temperature > 38.0 °C with valid thermal telemetry",
            risk_level=RiskLevel.HIGH,
            rule_source="Clinical Thermoregulation (Guyton & Hall; in-mission vital signs monitoring capability per NASA-STD-3001-VOL-1 Rev C [V1 3004])",
            source_version="Revision C / Guyton 14th Ed",
            intended_scope="In-flight core thermal monitoring",
            limitations="Peripheral skin temperature cannot be evaluated against core hyperthermia thresholds without validated conversion model",
            last_verification_date="2026-11-01",
            suggested_escalation=EscalationState.ESCALATION_RECOMMENDED,
            suggested_destination=EscalationDestination.FLIGHT_SURGEON,
            recommended_action="Verify physical sensor coupling; check for active infection or dehydration."
        )
        self._rules[rule_hyperthermia.rule_id] = rule_hyperthermia
        def _eval_hyperthermia(evs: Dict[str, NormalizedEvidenceItem]) -> Tuple[bool, str, List[str]]:
            ev = evs.get("temperature_mean")
            if not ev or ev.validity_status != EvidenceValidity.VALID:
                return False, "Valid temperature telemetry unavailable.", []
            meas_type = ev.raw_context.get("measurement_type") if ev.raw_context else None
            if meas_type == "SKIN_SURFACE_TEMPERATURE":
                return False, "Core body temperature measurement unavailable; peripheral skin surface temperature cannot be evaluated against core hyperthermia thresholds without validated conversion model.", []
            if float(ev.observed_value) > 38.0:
                return True, f"Core temperature {ev.observed_value:.2f} °C exceeds hyperthermia threshold of 38.0 °C.", [ev.evidence_id]
            return False, "Core temperature does not exceed 38.0 °C.", []
        self._evaluators[rule_hyperthermia.rule_id] = _eval_hyperthermia

        rule_co2 = RiskRule(
            rule_id="RR-ENV-CABIN-CO2-ELEVATED",
            rule_name="Elevated Atmospheric Carbon Dioxide Concentration",
            domain=RiskDomain.RESPIRATORY,
            required_variables=["cabin_co2_percent"],
            threshold_condition="Cabin atmospheric CO2 concentration > 0.70%",
            risk_level=RiskLevel.MODERATE,
            rule_source="NASA-STD-3001-VOL-2",
            source_version="Revision C",
            intended_scope="Spacecraft environmental life support",
            limitations="Localized pockets of uncirculated air in sleeping quarters may produce localized CO2 peaks",
            last_verification_date="2026-11-01",
            suggested_escalation=EscalationState.REVIEW_REQUIRED,
            suggested_destination=EscalationDestination.MISSION_CONTROL,
            recommended_action="Inspect environmental control scrubbers and increase cabin air mixing fans."
        )
        self._rules[rule_co2.rule_id] = rule_co2
        def _eval_co2(evs: Dict[str, NormalizedEvidenceItem]) -> Tuple[bool, str, List[str]]:
            ev = evs.get("cabin_co2_percent")
            if ev and ev.validity_status == EvidenceValidity.VALID and float(ev.observed_value) > 0.70:
                return True, f"Cabin CO2 concentration {ev.observed_value:.2f}% exceeds environmental guideline 0.70%.", [ev.evidence_id]
            return False, "Cabin CO2 concentration is within acceptable environmental limits.", []
        self._evaluators[rule_co2.rule_id] = _eval_co2

        rule_sensor_fail = RiskRule(
            rule_id="RR-DATA-SENSOR-CRITICAL-FAIL",
            rule_name="Critical Physiological Sensor Telemetry Failure",
            domain=RiskDomain.DATA_QUALITY_RELATED,
            required_variables=["ECG_quality_score"],
            threshold_condition="ECG sensor status is INVALID or reports fatal flatline/disconnect",
            risk_level=RiskLevel.HIGH,
            rule_source="TRUSTLINE-SQA-SYS-2026-V1.0",
            source_version="1.0",
            intended_scope="Automated signal gating",
            limitations="Does not reflect astronaut physiological disease; reflects loss of observational fidelity",
            last_verification_date="2026-11-01",
            suggested_escalation=EscalationState.REVIEW_REQUIRED,
            suggested_destination=EscalationDestination.FLIGHT_SURGEON,
            recommended_action="Prompt astronaut to adjust electrode placement and verify lead continuity."
        )
        self._rules[rule_sensor_fail.rule_id] = rule_sensor_fail
        def _eval_sensor_fail(evs: Dict[str, NormalizedEvidenceItem]) -> Tuple[bool, str, List[str]]:
            ev = evs.get("ECG_quality_score")
            if ev and ev.validity_status == EvidenceValidity.INVALID:
                return True, f"ECG sensor quality status is INVALID (Score: {ev.observed_value:.4f}).", [ev.evidence_id]
            return False, "ECG sensor telemetry is not classified as INVALID.", []
        self._evaluators[rule_sensor_fail.rule_id] = _eval_sensor_fail

        rule_sleep = RiskRule(
            rule_id="RR-FATIGUE-ACUTE-DEPRIVATION",
            rule_name="Acute Sleep Curtailment",
            domain=RiskDomain.SLEEP_AND_FATIGUE,
            required_variables=["actual_sleep_hours"],
            threshold_condition="Logged sleep duration < 5.0 hours in preceding 24h operational cycle",
            risk_level=RiskLevel.MODERATE,
            rule_source="NASA-BHO-STRESS-2024-V2.0",
            source_version="2.0",
            intended_scope="Behavioral health and cognitive performance",
            limitations="Short sleep may be tolerated acutely; cumulative chronic deficit carries higher risk",
            last_verification_date="2026-11-01",
            suggested_escalation=EscalationState.REVIEW_REQUIRED,
            suggested_destination=EscalationDestination.FLIGHT_SURGEON,
            recommended_action="Schedule sleep opportunity and consider cognitive workload throttling."
        )
        self._rules[rule_sleep.rule_id] = rule_sleep
        def _eval_sleep(evs: Dict[str, NormalizedEvidenceItem]) -> Tuple[bool, str, List[str]]:
            ev = evs.get("actual_sleep_hours")
            if ev and ev.validity_status == EvidenceValidity.VALID and float(ev.observed_value) < 5.0:
                return True, f"Logged sleep duration {ev.observed_value:.1f} hours indicates acute curtailment (< 5.0h).", [ev.evidence_id]
            return False, "Logged sleep duration is not below 5.0 hours.", []
        self._evaluators[rule_sleep.rule_id] = _eval_sleep

        rule_rad_acute = RiskRule(
            rule_id="RR-ENV-RADIATION-ACUTE",
            rule_name="Acute Space Radiation Exposure Exceeding SPE Action Threshold",
            domain=RiskDomain.GENERAL_PHYSIOLOGICAL,
            required_variables=["radiation_dose_rate_microgy_h"],
            threshold_condition="Absorbed space radiation dose rate > 500.0 µGy/h per NASA-STD-3001 SPE threshold",
            risk_level=RiskLevel.HIGH,
            rule_source="NASA-STD-3001-VOL-1 Rev C / NASA-STD-3001-VOL-2",
            source_version="Revision C",
            intended_scope="Spacecraft environmental radiation protection and storm shelter ingress",
            limitations="Dosimeter sensor must be calibrated and operational",
            last_verification_date="2026-11-14",
            suggested_escalation=EscalationState.ESCALATION_RECOMMENDED,
            suggested_destination=EscalationDestination.FLIGHT_SURGEON,
            recommended_action="Immediately terminate EVA; ingress to designated storm shelter and align protective shielding."
        )
        self._rules[rule_rad_acute.rule_id] = rule_rad_acute
        def _eval_rad_acute(evs: Dict[str, NormalizedEvidenceItem]) -> Tuple[bool, str, List[str]]:
            ev = evs.get("radiation_dose_rate_microgy_h")
            if ev and ev.validity_status == EvidenceValidity.VALID and float(ev.observed_value) > 500.0:
                return True, f"Space radiation dose rate {ev.observed_value:.1f} µGy/h exceeds NASA-STD-3001 action threshold 500.0 µGy/h.", [ev.evidence_id]
            return False, "Space radiation dose rate does not exceed 500.0 µGy/h.", []
        self._evaluators[rule_rad_acute.rule_id] = _eval_rad_acute

        rule_rad_cum = RiskRule(
            rule_id="RR-ENV-RADIATION-CUMULATIVE",
            rule_name="Cumulative 30-Day Mission Radiation Exposure Limit Reached",
            domain=RiskDomain.GENERAL_PHYSIOLOGICAL,
            required_variables=["radiation_cumulative_dose_msv"],
            threshold_condition="Cumulative equivalent radiation dose > 250.0 mSv per NASA-STD-3001 Table 2",
            risk_level=RiskLevel.HIGH,
            rule_source="NASA-STD-3001-VOL-1 Rev C Table 2",
            source_version="Revision C",
            intended_scope="Mission cumulative radiation budget monitoring",
            limitations="Cumulative calculation depends on continuous mission dosimetry logging",
            last_verification_date="2026-11-14",
            suggested_escalation=EscalationState.REVIEW_REQUIRED,
            suggested_destination=EscalationDestination.FLIGHT_SURGEON,
            recommended_action="Review remaining mission career exposure; evaluate crew rotation or EVA activity curtailment."
        )
        self._rules[rule_rad_cum.rule_id] = rule_rad_cum
        def _eval_rad_cum(evs: Dict[str, NormalizedEvidenceItem]) -> Tuple[bool, str, List[str]]:
            ev = evs.get("radiation_cumulative_dose_msv")
            if ev and ev.validity_status == EvidenceValidity.VALID and float(ev.observed_value) > 250.0:
                return True, f"Cumulative radiation dose {ev.observed_value:.1f} mSv exceeds NASA-STD-3001 30-day limit 250.0 mSv.", [ev.evidence_id]
            return False, "Cumulative radiation dose does not exceed 250.0 mSv.", []
        self._evaluators[rule_rad_cum.rule_id] = _eval_rad_cum

