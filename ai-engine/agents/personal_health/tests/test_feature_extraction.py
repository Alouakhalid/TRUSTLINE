"""Unit tests for multi-rate physiological feature extraction."""
import pytest
import numpy as np
from personal_health.services.feature_extraction_service import FeatureExtractionService

def test_feature_extraction_complete_streams(
    mock_ecg_stream,
    mock_eda_stream,
    mock_resp_stream,
    mock_temp_stream,
    mock_emg_stream,
    mock_acc_stream
):
    """Verify that all Core 14 features are extracted when all 6 streams are present."""
    svc = FeatureExtractionService()
    streams = {
        "ECG": mock_ecg_stream,
        "EDA": mock_eda_stream,
        "RESP": mock_resp_stream,
        "TEMP": mock_temp_stream,
        "EMG": mock_emg_stream,
        "ACC": mock_acc_stream
    }
    report = svc.extract_features(streams=streams, astronaut_id="AST-001", session_id="SES-001")
    assert report.has_valid_core14 is True
    assert report.core_features is not None

    feat_dict = report.core_features.to_feature_dict()
    assert len(feat_dict) == 14
    assert feat_dict["hr_mean_bpm"] > 50.0
    assert feat_dict["eda_mean"] > 0.0
    assert feat_dict["temp_mean"] == pytest.approx(33.5, rel=1e-2)
    assert feat_dict["acc_magnitude_mean"] == pytest.approx(0.98, rel=1e-2)

def test_ultra_short_term_hrv_labeling(mock_ecg_stream):
    """Verify that windows under 300 seconds are labeled as exploratory ultra-short-term."""
    svc = FeatureExtractionService(ultra_short_hrv_threshold_seconds=300.0)
    streams = {"ECG": mock_ecg_stream}
    report = svc.extract_features(streams=streams)

    hrv_features = [f for f in report.all_features if "hrv" in f.feature_name]
    assert len(hrv_features) > 0
    for hrv_feat in hrv_features:
        assert hrv_feat.exploratory_ultra_short_term is True

def test_feature_extraction_missing_ecg(mock_eda_stream):
    """Verify that missing core sensors flags incomplete core features."""
    svc = FeatureExtractionService()
    streams = {"EDA": mock_eda_stream}
    report = svc.extract_features(streams=streams)
    assert report.has_valid_core14 is False
    assert report.core_features is None
    assert len(report.extraction_warnings) > 0
