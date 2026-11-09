"""Cross-agent evidence registry and quarantine audit service for the Supervisor."""
from typing import Dict, List, Any
from ..schemas.assessment import EvidenceRegistryItem

class EvidenceRegistryService:
    """Consolidates evidence across Sensor Quality, Personal Health, and Risk Assessment agents."""

    @classmethod
    def compile_and_audit_registry(cls, state: Dict[str, Any]) -> List[EvidenceRegistryItem]:
        """Aggregate evidence items across upstream agent outputs and enforce scientific quarantine guards."""
        registry: List[EvidenceRegistryItem] = []

        sqr = state.get("sensor_quality_result") or {}
        sensors = sqr.get("sensors", {})
        for s_name, s_res in sensors.items():
            status_val = s_res.get("status")
            score = s_res.get("quality_score", 0.0)
            is_quarantined = status_val == "INVALID" or s_res.get("critical_failure", False)
            q_reason = None
            if is_quarantined:
                q_reason = f"Sensor {s_name} marked INVALID by DSP quality inspection engine (score={score:.4f})"
            registry.append(EvidenceRegistryItem(
                evidence_id=f"EV-SQ-{s_name}",
                source_agent="sensor_quality_agent",
                domain="DATA_QUALITY_RELATED",
                metric_name=f"{s_name}_quality_score",
                observed_value=score,
                validity_status=status_val or "VALID",
                is_quarantined=is_quarantined,
                quarantine_reason=q_reason,
                provenance=f"Sensor Quality Agent DSP Pipeline ({s_name})"
            ))

        pha = state.get("personal_health_result") or {}
        core_feats = pha.get("core_features") or {}
        hrv_diag = pha.get("hrv_diagnostics") or {}

        ecg_info = sensors.get("ECG", {})
        ecg_quarantined = ecg_info.get("status") == "INVALID" or ecg_info.get("critical_failure", False)

        resp_info = sensors.get("RESP", {})
        resp_quarantined = resp_info.get("status") == "INVALID" or resp_info.get("critical_failure", False)

        temp_info = sensors.get("TEMP", {})
        temp_quarantined = temp_info.get("status") == "INVALID" or temp_info.get("critical_failure", False)

        eda_info = sensors.get("EDA", {})
        eda_quarantined = eda_info.get("status") == "INVALID" or eda_info.get("critical_failure", False)

        if "hr_mean_bpm" in core_feats and core_feats["hr_mean_bpm"] is not None:
            registry.append(EvidenceRegistryItem(
                evidence_id="EV-PHY-HR-MEAN",
                source_agent="personal_health_agent",
                domain="CARDIOVASCULAR",
                metric_name="heart_rate_mean",
                observed_value=core_feats["hr_mean_bpm"],
                validity_status="INVALID" if ecg_quarantined else "VALID",
                is_quarantined=ecg_quarantined,
                quarantine_reason="Source ECG signal marked INVALID by DSP inspection" if ecg_quarantined else None,
                provenance="Personal Health Agent ECG Core-14 Extraction"
            ))

        rmssd = core_feats.get("hrv_rmssd_ms", 0.0)
        hrv_status = hrv_diag.get("hrv_status", "ZERO_VARIABILITY") if hrv_diag else "ZERO_VARIABILITY"
        is_hrv_invalid = rmssd < 1.0 or hrv_status == "ZERO_VARIABILITY" or ecg_quarantined
        q_reason = "Zero variability artifact detected; quarantined from autonomic cardiovascular inference"
        if ecg_quarantined:
            q_reason = "Source ECG signal marked INVALID by DSP inspection"
        registry.append(EvidenceRegistryItem(
            evidence_id="EV-PHY-HRV-RMSSD",
            source_agent="personal_health_agent",
            domain="CARDIOVASCULAR",
            metric_name="hrv_rmssd",
            observed_value=rmssd,
            validity_status="INVALID" if is_hrv_invalid else "VALID",
            is_quarantined=is_hrv_invalid,
            quarantine_reason=q_reason if is_hrv_invalid else None,
            provenance="Personal Health Agent ECG R-Peak Timing"
        ))

        if "resp_rate_bpm" in core_feats and core_feats["resp_rate_bpm"] is not None:
            registry.append(EvidenceRegistryItem(
                evidence_id="EV-PHY-RESP-RATE",
                source_agent="personal_health_agent",
                domain="RESPIRATORY",
                metric_name="respiratory_rate",
                observed_value=core_feats["resp_rate_bpm"],
                validity_status="INVALID" if resp_quarantined else "VALID",
                is_quarantined=resp_quarantined,
                quarantine_reason="Source RESP signal marked INVALID by DSP inspection" if resp_quarantined else None,
                provenance="Personal Health Agent Respiration Peak Frequency Analysis"
            ))

        if "temp_mean" in core_feats and core_feats["temp_mean"] is not None:
            t_validity = "INVALID" if temp_quarantined else "DEGRADED"
            t_reason = "Source TEMP signal marked INVALID by DSP inspection" if temp_quarantined else "Peripheral skin temperature; degraded for core thermoregulatory inference"
            registry.append(EvidenceRegistryItem(
                evidence_id="EV-PHY-TEMP-MEAN",
                source_agent="personal_health_agent",
                domain="THERMOREGULATORY",
                metric_name="temperature_mean",
                observed_value=core_feats["temp_mean"],
                validity_status=t_validity,
                is_quarantined=temp_quarantined,
                quarantine_reason=t_reason,
                provenance="Personal Health Agent Thermal Telemetry"
            ))

        if "eda_mean" in core_feats and core_feats["eda_mean"] is not None:
            registry.append(EvidenceRegistryItem(
                evidence_id="EV-PHY-EDA-MEAN",
                source_agent="personal_health_agent",
                domain="PSYCHOLOGICAL_AND_COGNITIVE",
                metric_name="eda_mean",
                observed_value=core_feats["eda_mean"],
                validity_status="INVALID" if eda_quarantined else "VALID",
                is_quarantined=eda_quarantined,
                quarantine_reason="Source EDA signal marked INVALID by DSP inspection" if eda_quarantined else None,
                provenance="Personal Health Agent Electrodermal Tonic Mean"
            ))

        symptoms = pha.get("symptom_findings", [])
        if not symptoms:
            registry.append(EvidenceRegistryItem(
                evidence_id="EV-SYM-UNSUBMITTED",
                source_agent="personal_health_agent",
                domain="GENERAL_PHYSIOLOGICAL",
                metric_name="symptom_status_unsubmitted",
                observed_value="no_symptoms_submitted",
                validity_status="NOT_AVAILABLE",
                is_quarantined=False,
                quarantine_reason="Unsubmitted symptoms represent unknown symptom status, not clinical absence of symptoms",
                provenance="Personal Health Intake (No Questionnaire Submitted)"
            ))
        else:
            for idx, sym in enumerate(symptoms):
                s_type = sym.get("symptom_type", f"reported_{idx+1}")
                s_cat = sym.get("symptom_category", "GENERAL_PHYSIOLOGICAL")
                s_sev = sym.get("severity", "nominal")
                registry.append(EvidenceRegistryItem(
                    evidence_id=f"EV-SYM-{idx+1}-{s_type.upper()}",
                    source_agent="personal_health_agent",
                    domain=s_cat if s_cat in ("CARDIOVASCULAR", "RESPIRATORY", "NEUROLOGICAL", "GENERAL_PHYSIOLOGICAL") else "GENERAL_PHYSIOLOGICAL",
                    metric_name=f"reported_symptom_{s_type}",
                    observed_value=sym.get("description") or s_type,
                    validity_status="VALID",
                    is_quarantined=False,
                    quarantine_reason=None,
                    provenance=f"Personal Health Agent Symptom Intake (Severity: {s_sev})"
                ))

        return registry
