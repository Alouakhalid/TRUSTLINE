"""Tests for explainability, SHAP fallback, and visualization modules."""
import pytest
from pathlib import Path
import numpy as np
from sensor_quality_agent.explainability.reason_codes import ReasonCode
from sensor_quality_agent.explainability.evidence_extractor import EvidenceExtractor
from sensor_quality_agent.explainability.shap_explainer import QualityShapExplainer
from sensor_quality_agent.explainability.explanation_engine import ExplanationEngine
from sensor_quality_agent.explainability.explanation_report import ExplanationReportFormatter
from sensor_quality_agent.schemas.signal_schema import SensorStreamData, QualityStatus
from sensor_quality_agent.schemas.output_schema import SensorQualityResult, SensorQualityMetrics, OverallQuality

def test_evidence_extractor_structure():
    ev = EvidenceExtractor.build_evidence(
        metric_name="test_metric",
        measured_value=0.42,
        threshold_value=0.30,
        units="ratio",
        confidence=0.95
    )
    assert ev.metric_name == "test_metric"
    assert ev.measured_value == 0.42
    assert ev.threshold_value == 0.30
    assert ev.confidence == 0.95

def test_shap_graceful_no_model_fallback():
    explainer = QualityShapExplainer(model=None)
    assert explainer.is_configured() is False
    res = explainer.explain_sample(np.array([1.0, 2.0, 3.0]))
    assert res["status"] == "NOT_CONFIGURED"
    assert "No machine-learning quality classification model is configured" in res["message"]

def test_explanation_engine_visualization(tmp_path: Path, clean_ecg_stream: SensorStreamData):
    engine = ExplanationEngine(output_dir=tmp_path)
    metrics = SensorQualityMetrics(
        valid_sample_ratio=1.0,
        missing_sample_ratio=0.0,
        artifact_ratio=0.0,
        flatline_ratio=0.0,
        noise_index=0.05,
        timestamp_integrity=1.0,
        saturation_ratio=0.0,
        continuity_score=1.0
    )
    res = SensorQualityResult(
        sensor="ECG",
        quality_score=0.98,
        status=QualityStatus.VALID,
        metrics=metrics,
        issues=[],
        recommendation="ACCEPT",
        critical_failure=False,
        sampling_rate=700.0,
        total_samples_analyzed=7000,
        duration_seconds=10.0
    )
    saved_path = engine.generate_sensor_diagnostic_plot(clean_ecg_stream, res)
    assert saved_path.exists()
    assert saved_path.suffix == ".png"

def test_explanation_report_formatting():
    metrics = SensorQualityMetrics(
        valid_sample_ratio=1.0,
        missing_sample_ratio=0.0,
        artifact_ratio=0.0,
        flatline_ratio=0.0,
        noise_index=0.0,
        timestamp_integrity=1.0,
        saturation_ratio=0.0,
        continuity_score=1.0
    )
    res = SensorQualityResult(
        sensor="ECG",
        quality_score=0.98,
        status=QualityStatus.VALID,
        metrics=metrics,
        issues=[],
        recommendation="ACCEPT",
        critical_failure=False,
        sampling_rate=700.0,
        total_samples_analyzed=7000,
        duration_seconds=10.0
    )
    overall = OverallQuality(
        score=0.98,
        status=QualityStatus.VALID,
        valid_sensors_count=1,
        total_sensors_count=1,
        degraded_sensors=[],
        rejected_sensors=[]
    )
    md = ExplanationReportFormatter.format_markdown_summary(overall, {"ECG": res})
    assert "Sensor Quality Assessment Summary" in md
    assert "ECG" in md
    assert "VALID" in md
