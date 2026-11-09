"""Service evaluating cross-modal evidence relationships, concordances, and contradictions."""
from typing import Dict, List, Optional, Any
from ..schemas.evidence import (
    RiskDomain,
    EvidenceValidity,
    NormalizedEvidenceItem
)

class CorrelatedEvidenceFinding(BaseModel := type("BaseModel", (), {})):
    """Cross-modal relationship identified between two or more evidence items."""
    def __init__(
        self,
        correlation_id: str,
        finding_type: str,
        domain: RiskDomain,
        primary_evidence_id: str,
        secondary_evidence_id: str,
        summary: str,
        is_concordant: bool = True
    ):
        self.correlation_id = correlation_id
        self.finding_type = finding_type
        self.domain = domain
        self.primary_evidence_id = primary_evidence_id
        self.secondary_evidence_id = secondary_evidence_id
        self.summary = summary
        self.is_concordant = is_concordant

class EvidenceCorrelationService:
    """Discovers clinical cross-modal concordances while strictly prohibiting diagnostic causation leaps."""

    @classmethod
    def evaluate_correlations(
        cls,
        evidence_items: List[NormalizedEvidenceItem]
    ) -> List[Dict[str, Any]]:
        """Identify cross-modal relationships among symptoms, sensors, and operational context."""
        findings: List[Dict[str, Any]] = []
        ev_by_metric: Dict[str, NormalizedEvidenceItem] = {e.metric_name: e for e in evidence_items}
        ev_by_id: Dict[str, NormalizedEvidenceItem] = {e.evidence_id: e for e in evidence_items}

        hr_ev = ev_by_metric.get("heart_rate_mean")
        chest_pain_sym = next((e for e in evidence_items if "chest_pain" in e.metric_name), None)
        if chest_pain_sym and hr_ev:
            if hr_ev.validity_status == EvidenceValidity.VALID and float(hr_ev.observed_value) > 100.0:
                findings.append({
                    "correlation_id": "CORR-CARDIO-CP-TACHY",
                    "finding_type": "SYMPTOM_PHYSIOLOGY_CONCORDANCE",
                    "domain": RiskDomain.CARDIOVASCULAR.value,
                    "primary_evidence_id": chest_pain_sym.evidence_id,
                    "secondary_evidence_id": hr_ev.evidence_id,
                    "summary": (
                        f"Subjective chest pain report correlates with validated resting tachycardia ({hr_ev.observed_value:.1f} bpm). "
                        "Notice: Correlation indicates physiological concordance; it does not confirm coronary pathology."
                    ),
                    "is_concordant": True
                })

        resp_ev = ev_by_metric.get("respiratory_rate")
        dyspnea_sym = next((e for e in evidence_items if "dyspnea" in e.metric_name or "shortness_of_breath" in e.metric_name), None)
        if dyspnea_sym and resp_ev:
            if resp_ev.validity_status == EvidenceValidity.VALID and float(resp_ev.observed_value) > 24.0:
                findings.append({
                    "correlation_id": "CORR-RESP-DYSP-TACHYPNEA",
                    "finding_type": "SYMPTOM_PHYSIOLOGY_CONCORDANCE",
                    "domain": RiskDomain.RESPIRATORY.value,
                    "primary_evidence_id": dyspnea_sym.evidence_id,
                    "secondary_evidence_id": resp_ev.evidence_id,
                    "summary": (
                        f"Subjective dyspnea correlates with validated resting tachypnea ({resp_ev.observed_value:.1f} breaths/min). "
                        "Notice: Correlation indicates respiratory elevation; clinical etiology requires physician assessment."
                    ),
                    "is_concordant": True
                })

        co2_ev = ev_by_metric.get("cabin_co2_percent")
        headache_sym = next((e for e in evidence_items if "headache" in e.metric_name), None)
        if co2_ev and headache_sym:
            if float(co2_ev.observed_value) > 0.5:
                findings.append({
                    "correlation_id": "CORR-ENV-CO2-HEADACHE",
                    "finding_type": "ENVIRONMENTAL_SYMPTOM_CONCORDANCE",
                    "domain": RiskDomain.NEUROLOGICAL.value,
                    "primary_evidence_id": co2_ev.evidence_id,
                    "secondary_evidence_id": headache_sym.evidence_id,
                    "summary": (
                        f"Elevated cabin atmospheric CO2 ({co2_ev.observed_value:.2f}%) correlates with reported headache. "
                        "Known spaceflight hypercapnia symptom concordance identified per NASA-STD-3001."
                    ),
                    "is_concordant": True
                })

        sleep_ev = ev_by_metric.get("actual_sleep_hours")
        fatigue_sym = next((e for e in evidence_items if "fatigue" in e.metric_name or "exhaustion" in e.metric_name), None)
        if sleep_ev and fatigue_sym:
            if float(sleep_ev.observed_value) < 6.0:
                findings.append({
                    "correlation_id": "CORR-SLEEP-FATIGUE",
                    "finding_type": "OPERATIONAL_FATIGUE_CONCORDANCE",
                    "domain": RiskDomain.SLEEP_AND_FATIGUE.value,
                    "primary_evidence_id": sleep_ev.evidence_id,
                    "secondary_evidence_id": fatigue_sym.evidence_id,
                    "summary": (
                        f"Documented sleep curtailment ({sleep_ev.observed_value:.1f} hrs) correlates with subjective fatigue complaint."
                    ),
                    "is_concordant": True
                })

        for sq_ev in [e for e in evidence_items if e.source_type.value == "sensor_quality"]:
            if sq_ev.validity_status == EvidenceValidity.INVALID:
                findings.append({
                    "correlation_id": f"CORR-QUALITY-{sq_ev.metric_name.upper()}",
                    "finding_type": "DATA_INTEGRITY_IMPACT",
                    "domain": RiskDomain.DATA_QUALITY_RELATED.value,
                    "primary_evidence_id": sq_ev.evidence_id,
                    "secondary_evidence_id": sq_ev.evidence_id,
                    "summary": (
                        f"Invalid sensor telemetry for {sq_ev.metric_name} prevents reliable autonomous physiological evaluation."
                    ),
                    "is_concordant": False
                })

        denied_sym = ev_by_metric.get("symptom_explicitly_denied")
        if denied_sym and hr_ev and hr_ev.validity_status == EvidenceValidity.VALID:
            if float(hr_ev.observed_value) > 120.0:
                findings.append({
                    "correlation_id": "CORR-CONFLICT-ASYMPTOMATIC-TACHYCARDIA",
                    "finding_type": "CROSS_MODAL_CONFLICT",
                    "domain": RiskDomain.CARDIOVASCULAR.value,
                    "primary_evidence_id": denied_sym.evidence_id,
                    "secondary_evidence_id": hr_ev.evidence_id,
                    "summary": (
                        f"Cross-modal conflict: Subjective symptom absence explicitly confirmed, but objective heart rate is elevated at {hr_ev.observed_value:.1f} bpm. "
                        "Reconciliation required by Flight Surgeon."
                    ),
                    "is_concordant": False
                })

        return findings
