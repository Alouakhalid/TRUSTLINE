"""Test suite verifying LLM clinical claim validation, grounding, and anti-hallucination boundaries."""
import pytest
from typing import Dict, Any

from personal_health.services.synthesis_validator import ClinicalSynthesisValidator

def test_01_reject_rmssd_normal_hallucination_on_zero_variance():
    """Verify claiming normal RMSSD or preserved vagal tone on zero variance rhythm is rejected."""
    validator = ClinicalSynthesisValidator()
    gt: Dict[str, Any] = {
        "rmssd_value": 0.0,
        "rmssd_status": "insufficient_variance"
    }
    synthesis = "Astronaut heart rate is 72 bpm. The RMSSD is normal and demonstrates preserved parasympathetic vagal tone."
    res = validator.validate_synthesis(synthesis, gt)

    assert res.is_valid is False
    assert any("RMSSD" in r or "parasympathetic" in r for r in res.rejections)

def test_02_reject_direct_vagus_nerve_measurement_overclaim():
    """Verify claiming RMSSD directly measures the vagus nerve is rejected."""
    validator = ClinicalSynthesisValidator()
    gt: Dict[str, Any] = {
        "rmssd_value": 45.0,
        "rmssd_status": "available"
    }
    synthesis = "Cardiac telemetry provides direct measurement of the vagus nerve via RR intervals."
    res = validator.validate_synthesis(synthesis, gt)

    assert res.is_valid is False
    assert any("vagus" in r.lower() or "overclaim" in r.lower() for r in res.rejections)

def test_03_reject_nominal_emergency_when_insufficient_data():
    """Verify claiming emergency status is nominal when deterministic state is INSUFFICIENT_DATA is rejected."""
    validator = ClinicalSynthesisValidator()
    gt: Dict[str, Any] = {
        "escalation_status": "INSUFFICIENT_DATA"
    }
    synthesis = "Vital signs are stable and emergency status is nominal with no alarms."
    res = validator.validate_synthesis(synthesis, gt)

    assert res.is_valid is False
    assert any("discrepancy" in r.lower() or "insufficient_data" in r.lower() for r in res.rejections)

def test_04_reject_unsupplied_mission_day():
    """Verify inventing mission elapsed day is rejected when not provided in telemetry."""
    validator = ClinicalSynthesisValidator()
    gt: Dict[str, Any] = {
        "mission_day": None
    }
    synthesis = "Telemetry recordings on Mission Day 6 reflect ongoing spaceflight adaptation."
    res = validator.validate_synthesis(synthesis, gt)

    assert res.is_valid is False
    assert any("Day 6" in r for r in res.rejections)

def test_05_reject_causal_cephalad_fluid_shift():
    """Verify attributing heart rate changes to cephalad fluid redistribution without evidence is rejected."""
    validator = ClinicalSynthesisValidator()
    gt: Dict[str, Any] = {
        "has_clinical_fluid_shift_evidence": False
    }
    synthesis = "Observed cardiovascular metrics stem from cephalad fluid redistribution and microgravity adaptation."
    res = validator.validate_synthesis(synthesis, gt)

    assert res.is_valid is False
    assert any("fluid" in r.lower() or "cephalad" in r.lower() for r in res.rejections)

def test_06_reject_unverified_asymptomatic_claim():
    """Verify zero unrecorded symptoms cannot be asserted as confirmed asymptomatic status."""
    validator = ClinicalSynthesisValidator()
    gt: Dict[str, Any] = {
        "symptom_count": 0,
        "symptom_confirmed_negative": False
    }
    synthesis = "The crew member remains asymptomatic throughout the monitoring period."
    res = validator.validate_synthesis(synthesis, gt)

    assert res.is_valid is False
    assert any("asymptomatic" in r.lower() or "symptom" in r.lower() for r in res.rejections)

def test_07_reject_wesad_broad_psychological_stability_claim():
    """Verify extrapolating WESAD acute stress model to broad psychological stability is rejected."""
    validator = ClinicalSynthesisValidator()
    gt: Dict[str, Any] = {}
    synthesis = "The ML classifier indicates the astronaut is in a state of psychological and physiological stability."
    res = validator.validate_synthesis(synthesis, gt)

    assert res.is_valid is False
    assert any("psychological" in r.lower() or "scope" in r.lower() for r in res.rejections)

def test_08_reject_baseline_registration_when_unavailable():
    """Verify recommending baseline registration when baseline_status is not_available is rejected."""
    validator = ClinicalSynthesisValidator()
    gt: Dict[str, Any] = {
        "baseline_status": "not_available"
    }
    synthesis = "We recommend registering this session as a personal baseline for future mission analysis."
    res = validator.validate_synthesis(synthesis, gt)

    assert res.is_valid is False
    assert any("baseline" in r.lower() for r in res.rejections)
