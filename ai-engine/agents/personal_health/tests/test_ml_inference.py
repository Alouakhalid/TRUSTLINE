"""Unit tests for production WESAD ML model inference service."""
import pytest
from personal_health.models.registry import ModelRegistry
from personal_health.services.ml_inference_service import MLInferenceService
from personal_health.schemas.physiological_features import Core14Features

def test_model_registry_metadata():
    """Verify registry loads 14 core features and model metadata."""
    reg = ModelRegistry()
    feats = reg.get_selected_features()
    assert len(feats) == 14
    assert feats[0] == "hr_mean_bpm"
    assert feats[-1] == "acc_magnitude_std"

    meta = reg.get_champion_model_metadata()
    assert meta.model_id == "HGB-WESAD-PROD-V1"
    assert meta.decision_threshold == 0.50
    assert "WESAD" in meta.training_dataset

def test_ml_inference_execution():
    """Verify calibrated inference and stress prediction."""
    svc = MLInferenceService()
    baseline_features = Core14Features(
        hr_mean_bpm=72.0,
        hr_std_bpm=5.0,
        hrv_rmssd_ms=50.0,
        hrv_sdnn_ms=65.0,
        eda_mean=4.0,
        eda_std=0.03,
        eda_iqr=0.04,
        resp_rate_bpm=15.0,
        resp_std=2.5,
        temp_mean=33.5,
        temp_std=0.05,
        emg_rms=0.012,
        acc_magnitude_mean=0.92,
        acc_magnitude_std=0.005
    )
    result = svc.predict_stress(baseline_features)
    assert 0.0 <= result.stress_probability <= 1.0
    assert result.verdict in ("NORMAL", "STRESS_ALERT")
    assert result.validity_status == "VALID"
    assert "WESAD" in result.clinical_disclaimer

def test_ml_inference_missing_feature():
    """Incomplete feature dictionary returns None rather than generating invalid inference."""
    svc = MLInferenceService()
    incomplete_map = {"hr_mean_bpm": 80.0}
    res = svc.predict_from_dict(incomplete_map)
    assert res is None
