"""End-to-end pipeline integration tests."""
import pytest
import json
from pathlib import Path
from sensor_quality_agent.schemas.input_schema import AstronautHealthManifest
from sensor_quality_agent.ingestion.signal_loader import SignalLoader
from sensor_quality_agent.core.quality_engine import QualityEngine
from sensor_quality_agent.services.report_builder import ReportBuilder
from sensor_quality_agent.schemas.output_schema import SensorQualityReport, QualityStatus
from sensor_quality_agent.main import run_sensor_quality_pipeline

def test_full_pipeline_with_sample_manifest():
    manifest_path = Path(__file__).resolve().parent.parent / "data" / "input" / "astronaut_health_data.json"
    assert manifest_path.exists()

    code = run_sensor_quality_pipeline(
        manifest_path=str(manifest_path),
        run_crew=False
    )
    assert code == 0

    report_path = Path(__file__).resolve().parent.parent / "data" / "output" / "sensor_quality_report.json"
    assert report_path.exists()

    with open(report_path, "r", encoding="utf-8") as f:
        data = json.load(f)

    report = SensorQualityReport(**data)
    assert report.astronaut_id == "AST-001"
    assert report.session_id == "SESSION-001"
    assert len(report.sensors) == 6
    assert "ECG" in report.sensors
    assert "EDA" in report.sensors
    assert "RESP" in report.sensors
    assert "EMG" in report.sensors
    assert "ACC" in report.sensors
    assert "TEMP" in report.sensors
    assert report.overall_quality.status in {QualityStatus.VALID, QualityStatus.ACCEPTABLE_WITH_WARNING}
    assert report.processing_decision.can_proceed is True
    assert len(report.visualizations) == 6

def test_partial_sensor_failure_isolation(tmp_path: Path):
    manifest_path = Path(__file__).resolve().parent.parent / "data" / "input" / "astronaut_health_data.json"
    with open(manifest_path, "r", encoding="utf-8") as f:
        manifest_dict = json.load(f)

    manifest = AstronautHealthManifest(**manifest_dict)
    loader = SignalLoader(base_dir=manifest_path.parent.parent)
    streams = loader.load_all_sensors(manifest, mmap=False)

    import numpy as np
    streams["ECG"].data = np.ones_like(streams["ECG"].data) * 2.0

    engine = QualityEngine()
    results, overall, decision = engine.inspect_all_streams(streams)

    assert results["ECG"].status == QualityStatus.INVALID
    assert results["ECG"].critical_failure is True
    assert results["EDA"].status != QualityStatus.INVALID
    assert results["RESP"].status != QualityStatus.INVALID
