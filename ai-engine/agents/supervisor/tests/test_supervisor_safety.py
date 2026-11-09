"""Safety and clinical constraint verification tests for the Supervisor Agent."""
import pytest
from supervisor.services.astronaut_communication_service import AstronautCommunicationService
from supervisor.services.evidence_registry_service import EvidenceRegistryService
from supervisor.workflow.nodes import final_synthesis_node
from supervisor.schemas.state import SupervisorMultiAgentState

def test_01_no_trigger_detected_semantics_never_claims_total_health():
    """Verify astronaut response clearly explains that NO_TRIGGER_DETECTED does not confirm absence of disease."""
    response = AstronautCommunicationService.generate_astronaut_response(
        astronaut_id="AST-001",
        session_id="SESSION-001",
        overall_risk="INSUFFICIENT_DATA",
        escalation_state="NO_TRIGGER_DETECTED",
        escalation_required=False,
        coverage_ratio=0.5,
        evaluated_domains=["CARDIOVASCULAR", "RESPIRATORY", "THERMOREGULATORY", "PSYCHOLOGICAL_AND_COGNITIVE", "DATA_QUALITY_RELATED"],
        unevaluated_domains=["NEUROLOGICAL", "SLEEP_AND_FATIGUE", "HYDRATION_AND_FLUID_BALANCE", "MUSCULOSKELETAL", "GENERAL_PHYSIOLOGICAL"],
        recommended_actions=[{"action_id": "ACT-NOM-001", "description": "Continue routine telemetry acquisition."}]
    )
    assert "No active emergency triggers or critical threshold violations were detected" in response
    assert "absence of telemetry from these areas means their status is unknown, not that health is confirmed nominal" in response

def test_02_insufficient_data_semantics_never_converts_to_low_risk():
    """Verify that partial domain coverage strictly preserves overall risk as INSUFFICIENT_DATA."""
    state: SupervisorMultiAgentState = {
        "astronaut_id": "AST-001",
        "session_id": "SESSION-001",
        "workflow_id": "WF-SAFE-01",
        "risk_assessment_result": {
            "overall_risk": "INSUFFICIENT_DATA",
            "overall_confidence": "MODERATE",
            "assessment_status": "PARTIALLY_COMPLETED",
            "coverage": {
                "total_domains": 10,
                "evaluated_domains": ["CARDIOVASCULAR", "RESPIRATORY"],
                "unevaluated_domains": ["NEUROLOGICAL", "SLEEP_AND_FATIGUE", "HYDRATION_AND_FLUID_BALANCE", "MUSCULOSKELETAL", "GENERAL_PHYSIOLOGICAL"],
                "domain_coverage_ratio": 0.2,
                "coverage_status": "PARTIAL"
            },
            "escalation": {
                "state": "NO_TRIGGER_DETECTED",
                "required": False,
                "urgency_level": "NOMINAL"
            }
        }
    }
    updates = final_synthesis_node(state)
    final_assessment = updates["final_assessment"]
    assert final_assessment["overall_risk"] == "INSUFFICIENT_DATA"
    assert final_assessment["workflow_completion_status"] == "PARTIALLY_COMPLETED"

def test_03_missing_symptoms_never_converted_to_negative_symptoms():
    """Verify unsubmitted symptoms are registered as NOT_AVAILABLE with explicit data gap quarantine reason."""
    state: SupervisorMultiAgentState = {
        "astronaut_id": "AST-001",
        "session_id": "SESSION-001",
        "personal_health_result": {
            "symptom_findings": []
        }
    }
    registry = EvidenceRegistryService.compile_and_audit_registry(state)
    sym_item = next((item for item in registry if item.evidence_id == "EV-SYM-UNSUBMITTED"), None)
    assert sym_item is not None
    assert sym_item.validity_status == "NOT_AVAILABLE"
    assert "Unsubmitted symptoms represent unknown symptom status, not clinical absence of symptoms" in sym_item.quarantine_reason

def test_04_evidence_provenance_preserved_across_all_registered_items():
    """Verify all evidence registry items contain non-empty provenance strings and source agents."""
    state: SupervisorMultiAgentState = {
        "astronaut_id": "AST-001",
        "session_id": "SESSION-001",
        "personal_health_result": {
            "core_features": {
                "hr_mean_bpm": 72.0,
                "hrv_rmssd_ms": 0.0,
                "resp_rate_bpm": 15.0,
                "temp_mean": 34.27,
                "eda_mean": 4.69
            }
        }
    }
    registry = EvidenceRegistryService.compile_and_audit_registry(state)
    assert len(registry) >= 5
    for item in registry:
        assert item.source_agent in ("sensor_quality_agent", "personal_health_agent", "risk_assessment_agent")
        assert len(item.provenance) > 5

def test_05_astronaut_communication_contains_required_safety_disclaimers():
    """Verify astronaut-facing text contains standard research prototype disclaimers and Flight Surgeon escalation path."""
    response = AstronautCommunicationService.generate_astronaut_response(
        astronaut_id="AST-001",
        session_id="SESSION-001",
        overall_risk="INSUFFICIENT_DATA",
        escalation_state="NO_TRIGGER_DETECTED",
        escalation_required=False,
        coverage_ratio=0.5,
        evaluated_domains=["CARDIOVASCULAR"],
        unevaluated_domains=["NEUROLOGICAL"],
        recommended_actions=[]
    )
    assert "TRUSTLINE is an investigational health-monitoring research prototype" in response
    assert "It does not replace independent Flight Surgeon clinical evaluation" in response
    assert "Flight Surgeon" in response

def test_06_astronaut_communication_strictly_grounds_hrv_rmssd_without_sensor_artifact_speculation():
    """Verify RMSSD zero variability is quarantined without claiming confirmed sensor artifact."""
    response = AstronautCommunicationService.generate_astronaut_response(
        astronaut_id="AST-001",
        session_id="SESSION-001",
        overall_risk="INSUFFICIENT_DATA",
        escalation_state="NO_TRIGGER_DETECTED",
        escalation_required=False,
        coverage_ratio=0.5,
        evaluated_domains=["CARDIOVASCULAR"],
        unevaluated_domains=["NEUROLOGICAL"],
        recommended_actions=[]
    )
    assert "EV-PHY-HRV-RMSSD" in response
    assert "INVALID" in response
    assert "ZERO_VARIABILITY" in response
    assert "quarantined from autonomic cardiovascular evaluation" in response
    assert "sensor artifact" not in response

def test_07_astronaut_communication_strictly_grounds_temperature_without_ambient_conditions_speculation():
    """Verify skin temperature is distinguished from core without asserting ambient conditions."""
    response = AstronautCommunicationService.generate_astronaut_response(
        astronaut_id="AST-001",
        session_id="SESSION-001",
        overall_risk="INSUFFICIENT_DATA",
        escalation_state="NO_TRIGGER_DETECTED",
        escalation_required=False,
        coverage_ratio=0.5,
        evaluated_domains=["THERMOREGULATORY"],
        unevaluated_domains=["NEUROLOGICAL"],
        recommended_actions=[]
    )
    assert "EV-PHY-TEMP-MEAN" in response
    assert "peripheral skin surface temperature" in response
    assert "core body temperature" in response
    assert "DEGRADED" in response
    assert "habitat ambient conditions" not in response

def test_08_astronaut_communication_strictly_grounds_cardiac_and_respiration_metrics():
    """Verify cardiac and respiration statements cite exact numbers, evidence IDs, and reference intervals."""
    response = AstronautCommunicationService.generate_astronaut_response(
        astronaut_id="AST-001",
        session_id="SESSION-001",
        overall_risk="INSUFFICIENT_DATA",
        escalation_state="NO_TRIGGER_DETECTED",
        escalation_required=False,
        coverage_ratio=0.5,
        evaluated_domains=["CARDIOVASCULAR", "RESPIRATORY"],
        unevaluated_domains=["NEUROLOGICAL"],
        recommended_actions=[],
        core_features={"hr_mean_bpm": 72.0, "resp_rate_bpm": 15.0}
    )
    assert "72.0 bpm" in response
    assert "EV-PHY-HR-MEAN" in response
    assert "15.0 breaths/min" in response
    assert "EV-PHY-RESP-RATE" in response
    assert "reference interval 50.0–100.0 bpm" in response
    assert "reference interval 10.0–22.0 breaths/min" in response

def test_09_astronaut_communication_uses_configured_monitoring_domains_terminology():
    """Verify coverage reporting uses configured monitoring domains instead of standard monitoring domains."""
    response = AstronautCommunicationService.generate_astronaut_response(
        astronaut_id="AST-001",
        session_id="SESSION-001",
        overall_risk="INSUFFICIENT_DATA",
        escalation_state="NO_TRIGGER_DETECTED",
        escalation_required=False,
        coverage_ratio=0.5,
        evaluated_domains=["CARDIOVASCULAR"],
        unevaluated_domains=["NEUROLOGICAL"],
        recommended_actions=[]
    )
    assert "configured monitoring domains" in response
    assert "standard monitoring domains" not in response

def test_10_astronaut_communication_preserves_unsubmitted_symptom_distinction():
    """Verify unsubmitted symptoms state unassessed status rather than confirmed absence."""
    response = AstronautCommunicationService.generate_astronaut_response(
        astronaut_id="AST-001",
        session_id="SESSION-001",
        overall_risk="INSUFFICIENT_DATA",
        escalation_state="NO_TRIGGER_DETECTED",
        escalation_required=False,
        coverage_ratio=0.5,
        evaluated_domains=["CARDIOVASCULAR"],
        unevaluated_domains=["NEUROLOGICAL"],
        recommended_actions=[],
        symptoms_reported=None
    )
    assert "EV-SYM-UNSUBMITTED" in response
    assert "unassessed symptom status" in response
    assert "must not be interpreted as a confirmed clinical absence" in response
