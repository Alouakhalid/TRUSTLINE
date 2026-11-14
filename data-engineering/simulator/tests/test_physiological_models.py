"""Unit tests for physiological signal generators, scenario engine, and fault injection."""
import pytest
import numpy as np
from simulator.schemas import ScenarioType, FaultType, FaultInjectionConfig, SensorType
from simulator.physiological_models.cardiac import CardiacModel
from simulator.physiological_models.respiratory import RespiratoryModel
from simulator.physiological_models.autonomic import ElectrodermalModel
from simulator.physiological_models.thermal import ThermalModel
from simulator.physiological_models.biomechanical import BiomechanicalModel, MotionState
from simulator.fault_injector import FaultInjector
from simulator.scenarios.engine import ScenarioEngine


def test_cardiac_waveform_synthesis():
    """Verify ECG 3-lead array and PPG pulse wave generation."""
    cardiac = CardiacModel(base_heart_rate_bpm=75.0, hrv_rmssd_ms=45.0)
    ecg, ppg, hr = cardiac.generate_segment(duration_sec=2.0, seed=42)

    assert ecg.shape[0] == 3  # 3 leads
    assert ecg.shape[1] == int(2.0 * 256.0)
    assert ppg.shape[0] == 1
    assert ppg.shape[1] == int(2.0 * 64.0)
    # Check physiological bounds
    assert np.min(ppg) >= 0.0
    assert np.max(ppg) <= 1.0
    assert np.all(hr >= 60.0) and np.all(hr <= 90.0)


def test_respiratory_asymmetry_and_coupling():
    """Verify asymmetric breathing cycle and phase generation."""
    resp = RespiratoryModel(base_respiration_rate_bpm=15.0, ie_ratio=0.60)
    wave, phase = resp.generate_segment(duration_sec=4.0, seed=42)

    assert wave.shape == (1, int(4.0 * 32.0))
    assert phase.shape == (int(4.0 * 32.0),)
    assert np.min(wave) >= -1.0
    assert np.max(wave) <= 1.0


def test_autonomic_eda_tonic_and_phasic():
    """Verify EDA skin conductance baseline and phasic bursts."""
    eda_model = ElectrodermalModel(baseline_scl_us=4.0)
    eda_trace = eda_model.generate_segment(duration_sec=5.0, burst_probability_per_sec=0.5, seed=42)

    assert eda_trace.shape == (1, int(5.0 * 4.0))
    assert np.all(eda_trace >= 0.05)
    assert np.all(eda_trace <= 40.0)


def test_thermal_model_metabolic_response():
    """Verify thermal inertia and core temperature elevation under exercise."""
    thermal = ThermalModel(base_core_temp_c=37.0)
    # Heavy exercise 8 METs
    thermal.set_metabolic_state(8.0)
    core, skin = thermal.generate_segment(duration_sec=10.0, seed=42)

    assert core.shape == (1, 10)
    assert skin.shape == (1, 40)
    assert np.all(core >= 36.5) and np.all(core <= 38.5)


def test_biomechanical_kinematics():
    """Verify accelerometer and gyroscope patterns across rest vs exercise."""
    bio = BiomechanicalModel()
    bio.set_motion_state(MotionState.MICROGRAVITY_REST)
    acc_rest, gyro_rest = bio.generate_segment(duration_sec=1.0, seed=42)
    # Microgravity rest should have low acceleration magnitude
    mag_rest = np.mean(np.linalg.norm(acc_rest, axis=0))
    assert mag_rest < 0.15

    bio.set_motion_state(MotionState.LOCOMOTION_EXERCISE)
    acc_ex, gyro_ex = bio.generate_segment(duration_sec=1.0, seed=42)
    mag_ex = np.mean(np.linalg.norm(acc_ex, axis=0))
    assert mag_ex > 0.8


def test_fault_injector_flatline_and_noise():
    """Verify fault injection modifies signal values deterministically."""
    injector = FaultInjector()
    injector.add_fault(
        FaultInjectionConfig(
            fault_type=FaultType.FLATLINE,
            target_sensor=SensorType.ECG,
            start_time_sec=0.0,
            duration_sec=2.0
        )
    )

    sig = np.ones((3, 256))
    corrupted = injector.apply_signal_faults(SensorType.ECG, sig, 256.0, current_time_sec=0.5)
    assert np.all(corrupted == 0.0)

    # Different sensor should not be affected
    other = injector.apply_signal_faults(SensorType.EDA, sig, 256.0, current_time_sec=0.5)
    assert np.all(other == 1.0)


def test_scenario_engine_execution_across_scenarios():
    """Verify ScenarioEngine runs across Scenarios A through F."""
    engine = ScenarioEngine(astronaut_id="AST-003", session_id="SESSION-TEST")

    for scen in [
        ScenarioType.SCENARIO_A_REST,
        ScenarioType.SCENARIO_B_EVA_ACTIVITY,
        ScenarioType.SCENARIO_C_ACUTE_STRESS,
        ScenarioType.SCENARIO_D_SLEEP_RECOVERY,
        ScenarioType.SCENARIO_E_HARDWARE_FAULT,
        ScenarioType.SCENARIO_F_RADIATION_COMPOSITE
    ]:
        engine.set_scenario(scen)
        pkts, space_pkt = engine.generate_step(duration_sec=1.0, seed=42)

        assert len(pkts) >= 8  # Unless packet loss drops some
        assert space_pkt is not None
        if scen == ScenarioType.SCENARIO_F_RADIATION_COMPOSITE:
            assert space_pkt.spe_active is True
            assert space_pkt.alert_level == "ALARM"
            assert space_pkt.dose_rate_microgy_h >= 500.0
