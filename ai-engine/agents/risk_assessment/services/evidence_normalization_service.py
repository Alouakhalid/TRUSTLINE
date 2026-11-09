"""Service standardizing multi-modal telemetry and clinical findings into normalized evidence."""
import uuid
from datetime import datetime
from typing import Dict, List, Optional, Any
from ..schemas.risk_input import RiskAssessmentInput
from ..schemas.evidence import (
    RiskDomain,
    EvidenceSourceType,
    EvidenceValidity,
    NormalizedEvidenceItem
)

class EvidenceNormalizationService:
    """Standardizes heterogeneous evidence into uniform, provenance-preserving evidence items."""

    SYMPTOM_DOMAIN_MAP: Dict[str, RiskDomain] = {
        "chest_pain": RiskDomain.CARDIOVASCULAR,
        "palpitations": RiskDomain.CARDIOVASCULAR,
        "tachycardia": RiskDomain.CARDIOVASCULAR,
        "bradycardia": RiskDomain.CARDIOVASCULAR,
        "dyspnea": RiskDomain.RESPIRATORY,
        "shortness_of_breath": RiskDomain.RESPIRATORY,
        "cough": RiskDomain.RESPIRATORY,
        "headache": RiskDomain.NEUROLOGICAL,
        "dizziness": RiskDomain.NEUROLOGICAL,
        "syncope": RiskDomain.NEUROLOGICAL,
        "loss_of_consciousness": RiskDomain.NEUROLOGICAL,
        "visual_disturbance": RiskDomain.NEUROLOGICAL,
        "insomnia": RiskDomain.SLEEP_AND_FATIGUE,
        "fatigue": RiskDomain.SLEEP_AND_FATIGUE,
        "exhaustion": RiskDomain.SLEEP_AND_FATIGUE,
        "somnolence": RiskDomain.SLEEP_AND_FATIGUE,
        "anxiety": RiskDomain.PSYCHOLOGICAL_AND_COGNITIVE,
        "stress": RiskDomain.PSYCHOLOGICAL_AND_COGNITIVE,
        "confusion": RiskDomain.PSYCHOLOGICAL_AND_COGNITIVE,
        "fever": RiskDomain.THERMOREGULATORY,
        "chills": RiskDomain.THERMOREGULATORY,
        "hypothermia": RiskDomain.THERMOREGULATORY,
        "thirst": RiskDomain.HYDRATION_AND_FLUID_BALANCE,
        "dehydration": RiskDomain.HYDRATION_AND_FLUID_BALANCE,
        "muscle_cramp": RiskDomain.MUSCULOSKELETAL,
        "back_pain": RiskDomain.MUSCULOSKELETAL,
        "joint_pain": RiskDomain.MUSCULOSKELETAL
    }

    @classmethod
    def normalize_all(cls, payload: RiskAssessmentInput) -> List[NormalizedEvidenceItem]:
        """Normalize all available streams and context into a uniform evidence collection."""
        evidence_list: List[NormalizedEvidenceItem] = []
        sensor_status_map: Dict[str, str] = {}

        if payload.sensor_quality_report is not None:
            sqr = payload.sensor_quality_report
            for s_name, s_res in sqr.sensors.items():
                sensor_status_map[s_name.upper()] = s_res.status.value.upper()
                s_validity = EvidenceValidity.VALID
                if s_res.status.value.upper() == "INVALID":
                    s_validity = EvidenceValidity.INVALID
                elif s_res.status.value.upper() in ("DEGRADED", "ACCEPTABLE_WITH_WARNING"):
                    s_validity = EvidenceValidity.DEGRADED

                evidence_list.append(
                    NormalizedEvidenceItem(
                        evidence_id=f"EV-SQ-{s_name.upper()}",
                        source_agent="sensor_quality_agent",
                        source_type=EvidenceSourceType.SENSOR_QUALITY,
                        domain=RiskDomain.DATA_QUALITY_RELATED,
                        metric_name=f"{s_name.upper()}_quality_score",
                        observed_value=s_res.quality_score,
                        unit="score",
                        validity_status=s_validity,
                        confidence=1.0,
                        quality_status=s_res.status.value,
                        source_reference=f"SQR:{sqr.session_id}:{s_name}",
                        evidence_description=(
                            f"Sensor {s_name.upper()} quality score {s_res.quality_score:.4f} "
                            f"(Status: {s_res.status.value}, Recommendation: {s_res.recommendation})."
                        ),
                        is_confirmed=True,
                        raw_context={"critical_failure": s_res.critical_failure, "issues": [i.reason_code for i in s_res.issues]}
                    )
                )

        if payload.personal_health_assessment is not None:
            pha = payload.personal_health_assessment

            if pha.core_features is not None:
                cf = pha.core_features

                ecg_status = sensor_status_map.get("ECG", "VALID")
                ecg_validity = EvidenceValidity.VALID if ecg_status == "VALID" else (
                    EvidenceValidity.INVALID if ecg_status == "INVALID" else EvidenceValidity.DEGRADED
                )
                evidence_list.append(
                    NormalizedEvidenceItem(
                        evidence_id="EV-PHY-HR-MEAN",
                        source_agent="personal_health_agent",
                        source_type=EvidenceSourceType.PHYSIOLOGICAL_MEASUREMENT,
                        domain=RiskDomain.CARDIOVASCULAR,
                        metric_name="heart_rate_mean",
                        observed_value=cf.hr_mean_bpm,
                        unit="bpm",
                        validity_status=ecg_validity,
                        confidence=0.95 if ecg_validity == EvidenceValidity.VALID else 0.50,
                        quality_status=ecg_status,
                        source_reference=f"PHA:{pha.assessment_id}:core_features:hr_mean_bpm",
                        evidence_description=f"Mean resting heart rate of {cf.hr_mean_bpm:.1f} bpm extracted from ECG."
                    )
                )

                hrv_note = ""
                hrv_validity = ecg_validity
                is_zero_var = False
                if pha.hrv_diagnostics is not None:
                    hrv_status_val = pha.hrv_diagnostics.hrv_status.value
                    hrv_note = f" (HRV Status: {hrv_status_val})"
                    if hrv_status_val == "ZERO_VARIABILITY":
                        hrv_validity = EvidenceValidity.INVALID
                        is_zero_var = True

                is_hrv_elig = (hrv_validity == EvidenceValidity.VALID)
                hrv_desc = (
                    f"Cardiac HRV RMSSD observed at {cf.hrv_rmssd_ms:.1f} ms{hrv_note}."
                    if is_hrv_elig
                    else f"Cardiac HRV RMSSD observed at {cf.hrv_rmssd_ms:.1f} ms{hrv_note}. Notice: Invalid HRV artifact cannot be evaluated as physiological evidence."
                )

                evidence_list.append(
                    NormalizedEvidenceItem(
                        evidence_id="EV-PHY-HRV-RMSSD",
                        source_agent="personal_health_agent",
                        source_type=EvidenceSourceType.PHYSIOLOGICAL_MEASUREMENT,
                        domain=RiskDomain.CARDIOVASCULAR,
                        metric_name="hrv_rmssd",
                        observed_value=cf.hrv_rmssd_ms,
                        unit="ms",
                        validity_status=hrv_validity,
                        confidence=0.90 if is_hrv_elig else 0.0,
                        quality_status=ecg_status,
                        evidence_classification="CLINICAL_OBSERVATION" if is_hrv_elig else "DATA_INTEGRITY_ARTIFACT",
                        is_eligible_for_risk=is_hrv_elig,
                        source_reference=f"PHA:{pha.assessment_id}:core_features:hrv_rmssd_ms",
                        evidence_description=hrv_desc,
                        raw_context={"hrv_status": pha.hrv_diagnostics.hrv_status.value if pha.hrv_diagnostics else "NORMAL", "zero_variability": is_zero_var}
                    )
                )

                eda_status = sensor_status_map.get("EDA", "VALID")
                eda_validity = EvidenceValidity.VALID if eda_status == "VALID" else (
                    EvidenceValidity.INVALID if eda_status == "INVALID" else EvidenceValidity.DEGRADED
                )
                evidence_list.append(
                    NormalizedEvidenceItem(
                        evidence_id="EV-PHY-EDA-MEAN",
                        source_agent="personal_health_agent",
                        source_type=EvidenceSourceType.PHYSIOLOGICAL_MEASUREMENT,
                        domain=RiskDomain.PSYCHOLOGICAL_AND_COGNITIVE,
                        metric_name="eda_mean",
                        observed_value=cf.eda_mean,
                        unit="uS",
                        validity_status=eda_validity,
                        confidence=0.95 if eda_validity == EvidenceValidity.VALID else 0.50,
                        quality_status=eda_status,
                        source_reference=f"PHA:{pha.assessment_id}:core_features:eda_mean",
                        evidence_description=f"Electrodermal skin conductance mean level of {cf.eda_mean:.2f} uS."
                    )
                )

                temp_status = sensor_status_map.get("TEMP", "VALID")
                temp_validity = EvidenceValidity.VALID if temp_status == "VALID" else (
                    EvidenceValidity.INVALID if temp_status == "INVALID" else EvidenceValidity.DEGRADED
                )
                evidence_list.append(
                    NormalizedEvidenceItem(
                        evidence_id="EV-PHY-TEMP-MEAN",
                        source_agent="personal_health_agent",
                        source_type=EvidenceSourceType.PHYSIOLOGICAL_MEASUREMENT,
                        domain=RiskDomain.THERMOREGULATORY,
                        metric_name="temperature_mean",
                        observed_value=cf.temp_mean,
                        unit="°C",
                        validity_status=temp_validity,
                        confidence=0.95 if temp_validity == EvidenceValidity.VALID else 0.50,
                        quality_status=temp_status,
                        evidence_classification="CLINICAL_OBSERVATION",
                        is_eligible_for_risk=True,
                        source_reference=f"PHA:{pha.assessment_id}:core_features:temp_mean",
                        evidence_description=(
                            f"Mean skin surface temperature recorded at {cf.temp_mean:.2f} °C "
                            f"(Sensor TEMP, sampling rate: 700.0 Hz, quality: {temp_status}). "
                            "Notice: Peripheral skin temperature cannot be evaluated against core body temperature clinical thresholds without an approved conversion model."
                        ),
                        raw_context={"sensor_source": "TEMP", "sampling_rate": 700.0, "measurement_type": "SKIN_SURFACE_TEMPERATURE", "quality_status": temp_status}
                    )
                )

                resp_status = sensor_status_map.get("RESP", "VALID")
                resp_validity = EvidenceValidity.VALID if resp_status == "VALID" else (
                    EvidenceValidity.INVALID if resp_status == "INVALID" else EvidenceValidity.DEGRADED
                )
                evidence_list.append(
                    NormalizedEvidenceItem(
                        evidence_id="EV-PHY-RESP-RATE",
                        source_agent="personal_health_agent",
                        source_type=EvidenceSourceType.PHYSIOLOGICAL_MEASUREMENT,
                        domain=RiskDomain.RESPIRATORY,
                        metric_name="respiratory_rate",
                        observed_value=cf.resp_rate_bpm,
                        unit="breaths/min",
                        validity_status=resp_validity,
                        confidence=0.90 if resp_validity == EvidenceValidity.VALID else 0.40,
                        quality_status=resp_status,
                        source_reference=f"PHA:{pha.assessment_id}:core_features:resp_rate_bpm",
                        evidence_description=f"Respiration rate computed at {cf.resp_rate_bpm:.1f} breaths/min."
                    )
                )

            for idx, mlf in enumerate(pha.ml_findings, start=1):
                evidence_list.append(
                    NormalizedEvidenceItem(
                        evidence_id=f"EV-ML-WESAD-{idx}",
                        source_agent="personal_health_agent",
                        source_type=EvidenceSourceType.EXPERIMENTAL_ML_CLASSIFIER,
                        domain=RiskDomain.PSYCHOLOGICAL_AND_COGNITIVE,
                        metric_name="experimental_lab_stress_probability",
                        observed_value=mlf.stress_probability,
                        unit="probability",
                        validity_status=EvidenceValidity.VALID,
                        confidence=0.85,
                        evidence_classification="EXPERIMENTAL_CONTEXT",
                        is_eligible_for_risk=False,
                        source_reference=f"PHA:{pha.assessment_id}:ml:{mlf.model_name}",
                        evidence_description=(
                            f"Experimental WESAD laboratory benchmark classifier '{mlf.model_name}' "
                            f"yielded acute laboratory stress probability {mlf.stress_probability:.4f} (verdict: {mlf.verdict}). "
                            "Notice: This is an experimental laboratory stress benchmark, not a clinical measure of astronaut distress."
                        ),
                        raw_context={"verdict": mlf.verdict, "version": mlf.version}
                    )
                )

        all_symptoms = list(payload.reported_symptoms)
        pha = payload.personal_health_assessment
        if pha is not None:
            all_symptoms.extend(pha.symptom_findings)

        explicit_denial = False
        seen_symptom_keys = set()
        for idx, sym in enumerate(all_symptoms, start=1):
            s_type = sym.symptom_type.lower()
            if s_type in ("none", "denies_symptoms", "no_symptoms", "asymptomatic", "no_complaints"):
                explicit_denial = True
                continue

            s_key = f"{sym.symptom_type}:{sym.description}".lower()
            if s_key in seen_symptom_keys:
                continue
            seen_symptom_keys.add(s_key)

            dom = cls.SYMPTOM_DOMAIN_MAP.get(s_type, RiskDomain.GENERAL_PHYSIOLOGICAL)
            sev_val = sym.severity.value if hasattr(sym.severity, "value") else (str(sym.severity) if sym.severity else "REPORTED")
            evidence_list.append(
                NormalizedEvidenceItem(
                    evidence_id=f"EV-SYM-{idx}",
                    source_agent="personal_health_agent",
                    source_type=EvidenceSourceType.REPORTED_SYMPTOM,
                    domain=dom,
                    metric_name=f"symptom_{s_type}",
                    observed_value=sev_val,
                    unit=None,
                    timestamp=sym.event_timestamp if hasattr(sym, "event_timestamp") else getattr(sym, "reported_at", datetime.utcnow()),
                    validity_status=EvidenceValidity.VALID,
                    confidence=0.90,
                    source_reference=f"SymptomEvent:{sym.event_id}",
                    evidence_description=f"Subjective complaint of {sym.symptom_type} (Severity: {sev_val}): {sym.description}.",
                    raw_context={"symptom_type": sym.symptom_type, "severity": sev_val}
                )
            )

        pha_symptom_status = getattr(pha, "symptom_assessment_status", None) if pha else None
        status_str = str(getattr(pha_symptom_status, "value", pha_symptom_status or ""))

        if explicit_denial or status_str == "CONFIRMED_ABSENCE_OF_SYMPTOMS":
            evidence_list.append(
                NormalizedEvidenceItem(
                    evidence_id="EV-SYM-CONFIRMED-ABSENCE",
                    source_agent="personal_health_agent",
                    source_type=EvidenceSourceType.REPORTED_SYMPTOM,
                    domain=RiskDomain.GENERAL_PHYSIOLOGICAL,
                    metric_name="symptom_explicitly_denied",
                    observed_value="confirmed_absence_of_symptoms",
                    unit=None,
                    timestamp=datetime.utcnow(),
                    validity_status=EvidenceValidity.VALID,
                    confidence=1.0,
                    source_reference="SymptomAssessmentStatus:CONFIRMED_ABSENCE_OF_SYMPTOMS",
                    evidence_description="Astronaut explicitly confirmed absence of subjective physical symptoms during structured assessment.",
                    is_confirmed=True
                )
            )
        elif not seen_symptom_keys and status_str == "NO_SYMPTOMS_REPORTED":
            evidence_list.append(
                NormalizedEvidenceItem(
                    evidence_id="EV-SYM-UNSUBMITTED",
                    source_agent="personal_health_agent",
                    source_type=EvidenceSourceType.REPORTED_SYMPTOM,
                    domain=RiskDomain.GENERAL_PHYSIOLOGICAL,
                    metric_name="symptom_status_unsubmitted",
                    observed_value="no_symptoms_submitted",
                    unit=None,
                    timestamp=datetime.utcnow(),
                    validity_status=EvidenceValidity.NOT_AVAILABLE,
                    confidence=0.0,
                    evidence_classification="UNSUBMITTED_STATUS",
                    is_eligible_for_risk=False,
                    source_reference="SymptomAssessmentStatus:NO_SYMPTOMS_REPORTED",
                    evidence_description="No subjective symptoms were submitted in this monitoring session; absence of reports does not establish clinical absence of symptoms.",
                    is_confirmed=False
                )
            )
        elif not seen_symptom_keys and (pha is None or status_str in ("SYMPTOM_DATA_UNAVAILABLE", "SYMPTOMS_NOT_ASSESSED", "")):
            evidence_list.append(
                NormalizedEvidenceItem(
                    evidence_id="EV-SYM-UNAVAILABLE",
                    source_agent="personal_health_agent",
                    source_type=EvidenceSourceType.REPORTED_SYMPTOM,
                    domain=RiskDomain.GENERAL_PHYSIOLOGICAL,
                    metric_name="symptom_data_unavailable",
                    observed_value="unavailable",
                    unit=None,
                    timestamp=datetime.utcnow(),
                    validity_status=EvidenceValidity.NOT_AVAILABLE,
                    confidence=0.0,
                    evidence_classification="UNSUBMITTED_STATUS",
                    is_eligible_for_risk=False,
                    source_reference="SymptomAssessment:UNAVAILABLE",
                    evidence_description="Subjective symptom assessment data is unavailable for this session.",
                    is_confirmed=False
                )
            )

        for idx, rec in enumerate(payload.confirmed_medical_records, start=1):
            evidence_list.append(
                NormalizedEvidenceItem(
                    evidence_id=f"EV-MED-CONFIRMED-{idx}",
                    source_agent="medical_records_repository",
                    source_type=EvidenceSourceType.CONFIRMED_MEDICAL_RECORD,
                    domain=RiskDomain.GENERAL_PHYSIOLOGICAL,
                    metric_name=rec.test_name.lower().replace(" ", "_"),
                    observed_value=rec.numeric_value if rec.numeric_value is not None else rec.value_string,
                    unit=rec.unit,
                    timestamp=rec.confirmation_timestamp,
                    validity_status=EvidenceValidity.VALID,
                    confidence=1.0,
                    source_reference=f"ConfirmedFinding:{rec.record_id}:Doc:{rec.document_id}",
                    evidence_description=(
                        f"Confirmed clinical finding: {rec.test_name} = {rec.value_string} "
                        f"{rec.unit or ''} (Ref: {rec.reference_range or 'N/A'}, Confirmed by: {rec.confirmed_by})."
                    ),
                    is_confirmed=True,
                    raw_context={"ref_range": rec.reference_range, "lab": rec.laboratory_name}
                )
            )

        for idx, evt in enumerate(payload.health_events, start=1):
            evidence_list.append(
                NormalizedEvidenceItem(
                    evidence_id=f"EV-EVT-{idx}",
                    source_agent="health_profile_repository",
                    source_type=EvidenceSourceType.HEALTH_EVENT,
                    domain=RiskDomain.GENERAL_PHYSIOLOGICAL,
                    metric_name="historical_health_event",
                    observed_value=evt.event_type,
                    timestamp=evt.event_time,
                    validity_status=EvidenceValidity.VALID,
                    confidence=1.0,
                    source_reference=f"HealthEvent:{evt.event_id}",
                    evidence_description=f"Historical health event: {evt.description} ({evt.severity}).",
                    is_historical=True
                )
            )

        ctx = payload.mission_context or (
            payload.personal_health_assessment.mission_context
            if payload.personal_health_assessment is not None
            else None
        )
        if ctx is not None and ctx.is_context_supplied:
            if ctx.is_eva_active:
                evidence_list.append(
                    NormalizedEvidenceItem(
                        evidence_id="EV-CTX-EVA-ACTIVE",
                        source_agent="mission_context_service",
                        source_type=EvidenceSourceType.MISSION_CONTEXT,
                        domain=RiskDomain.GENERAL_PHYSIOLOGICAL,
                        metric_name="is_eva_active",
                        observed_value=True,
                        validity_status=EvidenceValidity.VALID,
                        confidence=1.0,
                        source_reference=f"MissionContext:{ctx.mission_id}:eva",
                        evidence_description="Extravehicular Activity (EVA) is currently active."
                    )
                )
            if ctx.cabin_co2_percent is not None:
                evidence_list.append(
                    NormalizedEvidenceItem(
                        evidence_id="EV-CTX-CABIN-CO2",
                        source_agent="mission_context_service",
                        source_type=EvidenceSourceType.MISSION_CONTEXT,
                        domain=RiskDomain.RESPIRATORY,
                        metric_name="cabin_co2_percent",
                        observed_value=ctx.cabin_co2_percent,
                        unit="%",
                        validity_status=EvidenceValidity.VALID,
                        confidence=1.0,
                        source_reference=f"MissionContext:{ctx.mission_id}:cabin_co2",
                        evidence_description=f"Cabin atmospheric CO2 concentration observed at {ctx.cabin_co2_percent:.2f}%."
                    )
                )
            if ctx.actual_sleep_hours is not None:
                evidence_list.append(
                    NormalizedEvidenceItem(
                        evidence_id="EV-CTX-SLEEP-HOURS",
                        source_agent="mission_context_service",
                        source_type=EvidenceSourceType.MISSION_CONTEXT,
                        domain=RiskDomain.SLEEP_AND_FATIGUE,
                        metric_name="actual_sleep_hours",
                        observed_value=ctx.actual_sleep_hours,
                        unit="hours",
                        validity_status=EvidenceValidity.VALID,
                        confidence=0.90,
                        source_reference=f"MissionContext:{ctx.mission_id}:sleep",
                        evidence_description=f"Actual logged sleep duration: {ctx.actual_sleep_hours:.1f} hours."
                    )
                )

        return evidence_list
