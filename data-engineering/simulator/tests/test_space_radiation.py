"""Unit tests for Space Radiation Modeling and architectural ML isolation."""
import pytest
from simulator.space_environment.radiation_model import RadiationModel
from simulator.space_environment.nasa_standards import NASA_RADIATION_LIMITS
from simulator.space_environment.space_assessment_bridge import SpaceAssessmentBridge
from simulator.schemas import SpaceEnvironmentPacket

try:
    from risk_assessment.services.rule_registry import RuleRegistry
    from risk_assessment.schemas.evidence import NormalizedEvidenceItem, EvidenceValidity, RiskDomain
except ImportError:
    from agents.risk_assessment.services.rule_registry import RuleRegistry
    from agents.risk_assessment.schemas.evidence import NormalizedEvidenceItem, EvidenceValidity, RiskDomain


def test_radiation_model_baseline_and_shielding():
    """Verify GCR baseline rate and exponential aluminum shielding attenuation."""
    model = RadiationModel(baseline_gcr_dose_rate_microgy_h=25.0, shielding_thickness_g_cm2=10.0)
    dose_rate, eq_rate, alert = model.calculate_dose_rate(dt_sec=1.0)

    # With 10 g/cm2 shielding and mu=0.035, factor is exp(-0.35) ~ 0.7047
    expected_dose = 25.0 * 0.7047
    assert abs(dose_rate - expected_dose) < 1.0
    assert alert == "NOMINAL"
    assert eq_rate > 0.0


def test_radiation_model_spe_flare_and_alert():
    """Verify SPE proton surge triggers WARNING / ALARM alert states."""
    model = RadiationModel(baseline_gcr_dose_rate_microgy_h=20.0, shielding_thickness_g_cm2=5.0)
    # Trigger major solar storm
    model.trigger_solar_particle_event(peak_flux_pfu=2000.0)
    dose_rate, eq_rate, alert = model.calculate_dose_rate(dt_sec=1.0)

    assert dose_rate > NASA_RADIATION_LIMITS.spe_acute_action_threshold_microgy_h
    assert alert == "ALARM"
    assert eq_rate > 1.0  # Acute elevated mSv/h


def test_space_assessment_bridge_creates_valid_evidence():
    """Verify SpaceAssessmentBridge converts packet to NormalizedEvidenceItem records."""
    pkt = SpaceEnvironmentPacket(
        packet_id="RAD-TEST-001",
        timestamp_epoch_ms=1700000000000,
        dose_rate_microgy_h=620.0,
        equivalent_dose_rate_msv_h=1.35,
        cumulative_mission_dose_msv=265.0,
        spe_active=True,
        spe_flux_pfu=1800.0,
        shielding_thickness_g_cm2=10.0,
        alert_level="ALARM"
    )

    ev_items = SpaceAssessmentBridge.create_radiation_evidence_items(pkt)
    assert len(ev_items) == 2
    metrics = {item.metric_name: item for item in ev_items}

    assert "radiation_dose_rate_microgy_h" in metrics
    assert "radiation_cumulative_dose_msv" in metrics

    rate_item = metrics["radiation_dose_rate_microgy_h"]
    assert rate_item.observed_value == 620.0
    assert rate_item.validity_status == EvidenceValidity.VALID
    assert rate_item.domain == RiskDomain.GENERAL_PHYSIOLOGICAL


def test_radiation_rules_evaluation_in_rule_registry():
    """Verify RuleRegistry evaluates RR-ENV-RADIATION-ACUTE and RR-ENV-RADIATION-CUMULATIVE."""
    registry = RuleRegistry()
    acute_rule = registry.get_rule("RR-ENV-RADIATION-ACUTE")
    cum_rule = registry.get_rule("RR-ENV-RADIATION-CUMULATIVE")

    assert acute_rule is not None
    assert cum_rule is not None

    pkt = SpaceEnvironmentPacket(
        packet_id="RAD-TEST-002",
        timestamp_epoch_ms=1700000000000,
        dose_rate_microgy_h=580.0,  # Exceeds 500
        equivalent_dose_rate_msv_h=1.2,
        cumulative_mission_dose_msv=270.0,  # Exceeds 250
        spe_active=True,
        spe_flux_pfu=1200.0,
        shielding_thickness_g_cm2=10.0,
        alert_level="ALARM"
    )
    ev_items = SpaceAssessmentBridge.create_radiation_evidence_items(pkt)
    ev_dict = {item.metric_name: item for item in ev_items}

    # Evaluate Acute Rule
    is_trig_acute, trig_detail_acute, _ = registry.evaluate_rule("RR-ENV-RADIATION-ACUTE", ev_dict)
    assert is_trig_acute is True
    assert trig_detail_acute is not None
    assert "exceeds NASA-STD-3001 action threshold" in trig_detail_acute.rationale

    # Evaluate Cumulative Rule
    is_trig_cum, trig_detail_cum, _ = registry.evaluate_rule("RR-ENV-RADIATION-CUMULATIVE", ev_dict)
    assert is_trig_cum is True
    assert trig_detail_cum is not None
    assert "exceeds NASA-STD-3001 30-day limit" in trig_detail_cum.rationale


def test_strict_architectural_isolation_radiation_is_not_ml():
    """CRITICAL VERIFICATION: Prove radiation parameters NEVER enter ML features or pipelines."""
    # Test typical WESAD physiological ML feature set
    wesad_sample_features = [
        "hr_mean_bpm", "hr_std_bpm", "hrv_rmssd_ms", "resp_rate_bpm",
        "eda_mean", "temp_mean", "acc_magnitude_mean"
    ]
    # Standard WESAD must pass isolation verification
    assert SpaceAssessmentBridge.verify_ml_isolation(wesad_sample_features) is True

    # Intentionally injected radiation columns must be strictly detected and rejected
    contaminated_features = wesad_sample_features + ["radiation_dose_rate", "shielding_thickness"]
    assert SpaceAssessmentBridge.verify_ml_isolation(contaminated_features) is False
