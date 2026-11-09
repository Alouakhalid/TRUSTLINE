"""Regression test suite for Clinical Synthesis safety and anti-hallucination guardrails."""
import pytest
from typing import Dict, Any

from personal_health.services.synthesis_validator import (
    ClinicalSynthesisValidator,
    SynthesisValidationResult
)
from personal_health.agent.agent import generate_clinical_synthesis
from personal_health.agent.prompts import build_clinical_synthesis_prompt

def test_grounded_fallback_passes_validation():
    """Verify that deterministic grounded fallback satisfies all safety boundaries."""
    validator = ClinicalSynthesisValidator()
    gt: Dict[str, Any] = {
        "astronaut_id": "ASTRO-TEST",
        "session_id": "SESS-AUDIT-001",
        "hr_value": 72.0,
        "rmssd_value": 0.0,
        "rmssd_status": "insufficient_variance",
        "eda_value": 4.69,
        "hgb_prob": 0.1201,
        "hgb_verdict": "NORMAL",
        "mission_day": None,
        "has_clinical_fluid_shift_evidence": False,
        "symptom_count": 0,
        "symptom_confirmed_negative": False,
        "baseline_status": "not_available",
        "has_resp_measurement": False,
        "has_acc_measurement": False,
    }
    fallback_text = validator.generate_grounded_fallback(gt)
    result = validator.validate_synthesis(fallback_text, gt)

    assert result.is_valid is True
    assert len(result.rejection_reasons) == 0
    assert "Day 6" not in fallback_text
    assert "fluid redistribution" not in fallback_text
    assert "cephalad" not in fallback_text
    assert "asymptomatic" not in fallback_text
    assert "psychologically stable" not in fallback_text
    assert "must not be registered as an established personal baseline" in fallback_text

def test_validator_rejects_rmssd_hallucination():
    """Verify that claiming normal parasympathetic tone on RMSSD=0.0 ms is caught and rejected."""
    validator = ClinicalSynthesisValidator()
    gt: Dict[str, Any] = {
        "rmssd_value": 0.0,
        "rmssd_status": "insufficient_variance"
    }
    hallucinated_text = (
        "Astronaut heart rate is 72.0 bpm. The RMSSD is normal and indicates preserved "
        "parasympathetic tone during the mission."
    )
    result = validator.validate_synthesis(hallucinated_text, gt)
    assert result.is_valid is False
    assert any("RMSSD" in r or "parasympathetic" in r for r in result.rejection_reasons)

def test_validator_rejects_unsupplied_mission_day():
    """Verify that mentioning Mission Day when telemetry elapsed time is absent is rejected."""
    validator = ClinicalSynthesisValidator()
    gt: Dict[str, Any] = {"mission_day": None}
    hallucinated_text = (
        "Telemetry observations on Mission Day 6 indicate physiological adaptation."
    )
    result = validator.validate_synthesis(hallucinated_text, gt)
    assert result.is_valid is False
    assert any("Mission Day 6" in r for r in result.rejection_reasons)

def test_validator_rejects_fluid_shift_attribution():
    """Verify that attributing HR changes to cephalad fluid shift without evidence is rejected."""
    validator = ClinicalSynthesisValidator()
    gt: Dict[str, Any] = {"has_clinical_fluid_shift_evidence": False}
    hallucinated_text = (
        "Heart rate adjustments reflect cephalad fluid redistribution typical of orbital flight."
    )
    result = validator.validate_synthesis(hallucinated_text, gt)
    assert result.is_valid is False
    assert any("fluid" in r.lower() or "cephalad" in r.lower() for r in result.rejection_reasons)

def test_validator_rejects_false_asymptomatic_claim():
    """Verify that converting 0 unrecorded symptoms into confirmed asymptomatic status is rejected."""
    validator = ClinicalSynthesisValidator()
    gt: Dict[str, Any] = {
        "symptom_count": 0,
        "symptom_confirmed_negative": False
    }
    hallucinated_text = (
        "The astronaut remains completely asymptomatic throughout the telemetry observation period."
    )
    result = validator.validate_synthesis(hallucinated_text, gt)
    assert result.is_valid is False
    assert any("asymptomatic" in r.lower() or "symptom" in r.lower() for r in result.rejection_reasons)

def test_validator_rejects_ml_scope_overclaim():
    """Verify that claiming psychological or medical stability from WESAD classifier is rejected."""
    validator = ClinicalSynthesisValidator()
    gt: Dict[str, Any] = {}
    hallucinated_text = (
        "The WESAD stress model verdict confirms that the astronaut is psychologically stable and healthy."
    )
    result = validator.validate_synthesis(hallucinated_text, gt)
    assert result.is_valid is False
    assert any("psychological" in r.lower() or "scope" in r.lower() for r in result.rejection_reasons)

def test_validator_rejects_baseline_recommendation_when_unavailable():
    """Verify that recommending baseline registration when baseline is not_available is rejected."""
    validator = ClinicalSynthesisValidator()
    gt: Dict[str, Any] = {"baseline_status": "not_available"}
    hallucinated_text = (
        "Flight surgeons recommend registering this session as a personal baseline for future comparisons."
    )
    result = validator.validate_synthesis(hallucinated_text, gt)
    assert result.is_valid is False
    assert any("baseline" in r.lower() for r in result.rejection_reasons)

def test_exact_audit_scenario_clinical_synthesis():
    """Verify the exact audit scenario output satisfies all clinical safety constraints."""
    gt: Dict[str, Any] = {
        "astronaut_id": "ASTRO-01",
        "session_id": "SESS-VAL-001",
        "hr_value": 72.0,
        "rmssd_value": 0.0,
        "rmssd_status": "insufficient_variance",
        "eda_value": 4.69,
        "hgb_prob": 0.1201,
        "hgb_verdict": "NORMAL",
        "mission_day": None,
        "has_clinical_fluid_shift_evidence": False,
        "symptom_count": 0,
        "symptom_confirmed_negative": False,
        "baseline_status": "not_available",
        "has_resp_measurement": False,
        "has_acc_measurement": False,
    }
    evidence_summary = (
        "Astronaut: ASTRO-01 | Session: SESS-VAL-001\n"
        "Overall Quality: 0.964 (EXCELLENT)\n"
        "Physiology: HR=72.0 bpm, RMSSD=0.0 ms (INVALID - INSUFFICIENT VARIANCE), EDA=4.69 uS\n"
        "ML Stress Verdict: NORMAL (Prob=0.1201)\n"
        "Reported Symptoms Count: 0\n"
        "Baseline Status: not_available\n"
        "Escalation Required: False (NOMINAL)"
    )

    synthesis = generate_clinical_synthesis(
        astronaut_id="ASTRO-01",
        session_id="SESS-VAL-001",
        evidence_summary=evidence_summary,
        ground_truth=gt
    )

    assert synthesis is not None
    lower = synthesis.lower()

    assert "day 6" not in lower
    assert "fluid redistribution" not in lower
    assert "cephalad" not in lower
    assert "is asymptomatic" not in lower
    assert "remains asymptomatic" not in lower
    assert "confirmed asymptomatic" not in lower
    assert "psychologically stable" not in lower
    assert "psychological and physiological stability" not in lower
    assert "respiratory rate" not in lower
    assert "motor activity" not in lower
    assert "recommend registering this session as a personal baseline" not in lower

    validator = ClinicalSynthesisValidator()
    result = validator.validate_synthesis(synthesis, gt)
    assert result.is_valid is True
    assert len(result.rejection_reasons) == 0
