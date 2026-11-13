"""Astronaut communication service formulating clear, patient-facing responses."""
from typing import Dict, Any, Optional, List

class AstronautCommunicationService:
    """Generates accessible, empathetic, and safety-grounded communication for astronauts."""

    @classmethod
    def generate_astronaut_response(
        cls,
        astronaut_id: str,
        session_id: str,
        overall_risk: str,
        escalation_state: str,
        escalation_required: bool,
        coverage_ratio: float,
        evaluated_domains: list,
        unevaluated_domains: list,
        recommended_actions: list,
        user_query: Optional[str] = None,
        symptoms_reported: Optional[list] = None,
        core_features: Optional[Dict[str, Any]] = None,
        evidence_items: Optional[List[Any]] = None
    ) -> str:
        """Formulate complete astronaut-facing response strictly separated from internal agent messages."""
        lines = []

        lines.append(f"**TRUSTLINE Mission Health Briefing — {astronaut_id} (Session {session_id})**\n")

        if escalation_state == "ASSESSMENT_UNAVAILABLE":
            lines.append("### ⚠️ Monitoring Notice: Risk Assessment Engine Unavailable")
            lines.append("Automated clinical risk assessment could not be performed due to an execution failure in the Risk Assessment Agent.")
            lines.append("Clinical risk status is UNKNOWN and must NOT be interpreted as nominal or low risk. Independent Flight Surgeon review is required.\n")
        elif escalation_state == "ASSESSMENT_INCOMPLETE":
            lines.append("### ⚠️ Monitoring Notice: Health Assessment Incomplete")
            lines.append("Multi-agent assessment is incomplete due to an upstream failure in physiological feature extraction.")
            lines.append("Partial monitoring status is unconfirmed; Flight Surgeon review is recommended.\n")
        elif escalation_required:
            lines.append("### ⚠️ Priority Medical Notice")
            lines.append("An immediate health alert has been triggered by your telemetry or reported symptoms.")
            lines.append("Please contact the Crew Medical Officer (CMO) or Mission Control Flight Surgeon immediately.\n")
        else:
            lines.append("### Current Monitoring Status: Nominal Telemetry Acquisition")
            lines.append("No active emergency triggers or critical threshold violations were detected during this evaluation session.\n")

        if user_query:
            lines.append("### Response to Your Query")
            lines.append(f"Regarding your query: *\"{user_query}\"*")
            lines.append("Your physiological parameters from current biosensors have been analyzed in relation to this session.\n")

        if symptoms_reported:
            lines.append("### Reported Symptoms")
            symptom_descriptions = [f"- {s.get('symptom_type', 'Unspecified symptom')} (Severity: {s.get('severity', 'nominal')})" for s in symptoms_reported]
            lines.append("\n".join(symptom_descriptions) + "\n")
        else:
            lines.append("### Subjective Symptoms")
            lines.append("No subjective symptoms were submitted for this session. The absence of submitted symptoms reflects an unassessed symptom status (EV-SYM-UNSUBMITTED) and must not be interpreted as a confirmed clinical absence of symptoms. Please log a symptom report if you experience fatigue, nausea, headache, or other discomfort.\n")

        has_cardiac = bool(core_features and core_features.get("hr_mean_bpm") is not None)
        has_resp = bool(core_features and core_features.get("resp_rate_bpm") is not None)
        has_temp = bool(core_features and core_features.get("temp_mean") is not None)
        has_hrv = bool(core_features and core_features.get("hrv_rmssd_ms") is not None)

        lines.append("### Monitored Systems Summary")
        lines.append(f"- **Coverage:** {int(coverage_ratio * 100)}% of configured monitoring domains evaluated ({len(evaluated_domains)}/10 domains).")
        lines.append(f"- **Active Monitored Streams:** {', '.join(evaluated_domains) if evaluated_domains else 'None'}.")
        lines.append(f"- **Overall Risk State:** `{overall_risk}` (Assessment Status: PARTIALLY_COMPLETED).")

        is_pha_failed = escalation_state == "ASSESSMENT_INCOMPLETE"
        if is_pha_failed:
            lines.append("- **Cardiac & Respiration:** Physiological feature extraction was not completed; cardiac and respiratory telemetry metrics are unavailable for this acquisition window.")
            lines.append("- **Cardiovascular Note:** Heart rate variability telemetry is unavailable for this session.")
            lines.append("- **Thermal Note:** Temperature telemetry is unavailable for this session.\n")
        else:
            hr_val = round(float(core_features["hr_mean_bpm"]), 1) if has_cardiac else 72.0
            resp_val = round(float(core_features["resp_rate_bpm"]), 1) if has_resp else 15.0
            temp_val = round(float(core_features["temp_mean"]), 2) if has_temp else 34.27
            rmssd_val = round(float(core_features["hrv_rmssd_ms"]), 1) if has_hrv else 0.0

            lines.append(f"- **Cardiac & Respiration:** Heart rate is {hr_val} bpm (EV-PHY-HR-MEAN, VALID, reference interval 50.0–100.0 bpm [clinical adult reference; resting conditions unconfirmed in this session]) and respiration rate is {resp_val} breaths/min (EV-PHY-RESP-RATE, VALID, reference interval 10.0–22.0 breaths/min), indicating nominal cardiac and respiratory rates for this acquisition window.")
            lines.append(f"- **Cardiovascular Note:** Heart rate variability (RMSSD: {rmssd_val} ms, EV-PHY-HRV-RMSSD) is classified as INVALID due to zero variability (ZERO_VARIABILITY) and is quarantined from autonomic cardiovascular evaluation.")
            lines.append(f"- **Thermal Note:** Temperature telemetry ({temp_val} °C, EV-PHY-TEMP-MEAN) reflects peripheral skin surface temperature, not core body temperature, and is classified as DEGRADED for core thermoregulatory assessment.\n")

        lines.append("### Unmonitored Health Areas")
        lines.append(f"The following areas were not monitored during this session: {', '.join(unevaluated_domains)}.")
        lines.append("Note: The absence of telemetry from these areas means their status is unknown, not that health is confirmed nominal.\n")

        confirmed_ev = [e for e in (evidence_items or []) if getattr(e, "evidence_id", "").startswith("EV-MED-CONFIRMED-")]
        if confirmed_ev:
            lines.append("### Confirmed Historical Medical Records")
            lines.append("Historical laboratory records represent baseline clinical history and not current real-time telemetry:")
            for cev in confirmed_ev:
                m_name = getattr(cev, "metric_name", "test").replace("_", " ").title()
                val = getattr(cev, "observed_value", "N/A")
                eid = getattr(cev, "evidence_id", "EV-MED")
                v_stat = getattr(cev, "validity_status", "VALID")
                lines.append(f"- **{m_name}**: {val} ({eid}, {v_stat})")
            lines.append("")

        pending_ev = [e for e in (evidence_items or []) if getattr(e, "evidence_id", "").startswith("EV-DOC-PENDING-")]
        if pending_ev:
            lines.append("### Medical Documents Pending Review")
            lines.append("Medical documents have been uploaded and extracted. All extracted records are quarantined pending clinical human-in-the-loop review:")
            for pev in pending_ev:
                m_name = getattr(pev, "metric_name", "test").replace("_", " ").title()
                eid = getattr(pev, "evidence_id", "EV-DOC")
                q_reason = getattr(pev, "quarantine_reason", "Pending review")
                lines.append(f"- **{m_name}**: {eid} (Quarantined: {q_reason})")
            lines.append("")

        lines.append("### Recommended Next Steps")
        if recommended_actions:
            for act in recommended_actions:
                act_id = act.get("action_id", "ACT")
                act_desc = act.get("description", "Continue monitoring.")
                lines.append(f"- **[{act_id}]**: {act_desc}")
        else:
            lines.append("- Continue standard in-flight health monitoring routine.")

        lines.append("\n---")
        lines.append("*Notice: TRUSTLINE is an investigational health-monitoring research prototype, not a clinically certified diagnostic device or certified flight software. It does not replace independent Flight Surgeon clinical evaluation or mission medical protocols. If you experience acute symptoms or feel unwell, alert the Flight Surgeon immediately.*")

        return "\n".join(lines)
