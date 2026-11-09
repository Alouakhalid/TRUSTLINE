"""Stress Test 01: Missing sensor telemetry streams (individual, multiple, all)."""
import copy
import json
import pytest
from pathlib import Path
from supervisor.config.settings import get_supervisor_settings
from supervisor.workflow.graph import SupervisorWorkflowRunner
from supervisor.schemas.requests import SupervisorRequest, AstronautInput, InputModality
from sensor_quality.schemas.input_schema import AstronautHealthManifest
from sensor_quality.core.quality_engine import QualityEngine
from sensor_quality.ingestion.signal_loader import SignalLoader

def _load_base_manifest():
    cfg = get_supervisor_settings()
    manifest_file = cfg.sensor_quality_dir / "data" / "input" / "astronaut_health_data.json"
    with open(manifest_file, "r", encoding="utf-8") as f:
        return json.load(f), manifest_file

def test_01_missing_ecg_telemetry_stream(tmp_path):
    """Verify that omitting ECG prevents cardiovascular normality claims and attenuates coverage."""
    raw_manifest, _ = _load_base_manifest()
    manifest_no_ecg = copy.deepcopy(raw_manifest)
    manifest_no_ecg["signals"].pop("ECG", None)

    manifest_path = tmp_path / "manifest_no_ecg.json"
    with open(manifest_path, "w", encoding="utf-8") as f:
        json.dump(manifest_no_ecg, f)

    request = SupervisorRequest(
        request_id="REQ-STRESS-01-ECG",
        astronaut_id="AST-001",
        session_id="SESSION-001",
        modality=InputModality.MULTIMODAL,
        input_data=AstronautInput(sensor_manifest_path=str(manifest_path))
    )

    runner = SupervisorWorkflowRunner()
    result = runner.run_pipeline(request=request)

    assert result.get("overall_risk") in ("INSUFFICIENT_DATA", "UNKNOWN")
    ra_summary = result.get("risk_assessment_result") or {}
    cov = ra_summary.get("coverage") or {}
    assert "CARDIOVASCULAR" not in cov.get("evaluated_domains", [])
    assert result.get("workflow_status") in ("COMPLETED", "PARTIALLY_COMPLETED")

    reg = result.get("evidence_registry") or []
    hr_item = next((item for item in reg if item.get("evidence_id") == "EV-PHY-HR-MEAN"), None)
    assert hr_item is None or hr_item.get("validity_status") != "VALID"

def test_02_missing_eda_telemetry_stream(tmp_path):
    """Verify that omitting EDA prevents psychological autonomic claims."""
    raw_manifest, _ = _load_base_manifest()
    manifest_no_eda = copy.deepcopy(raw_manifest)
    manifest_no_eda["signals"].pop("EDA", None)

    manifest_path = tmp_path / "manifest_no_eda.json"
    with open(manifest_path, "w", encoding="utf-8") as f:
        json.dump(manifest_no_eda, f)

    request = SupervisorRequest(
        request_id="REQ-STRESS-01-EDA",
        astronaut_id="AST-001",
        session_id="SESSION-001",
        modality=InputModality.MULTIMODAL,
        input_data=AstronautInput(sensor_manifest_path=str(manifest_path))
    )

    runner = SupervisorWorkflowRunner()
    result = runner.run_pipeline(request=request)

    reg = result.get("evidence_registry") or []
    eda_item = next((item for item in reg if item.get("evidence_id") == "EV-PHY-EDA-MEAN"), None)
    assert eda_item is None

def test_03_missing_resp_telemetry_stream(tmp_path):
    """Verify that omitting RESP prevents respiratory rate inference."""
    raw_manifest, _ = _load_base_manifest()
    manifest_no_resp = copy.deepcopy(raw_manifest)
    manifest_no_resp["signals"].pop("RESP", None)

    manifest_path = tmp_path / "manifest_no_resp.json"
    with open(manifest_path, "w", encoding="utf-8") as f:
        json.dump(manifest_no_resp, f)

    request = SupervisorRequest(
        request_id="REQ-STRESS-01-RESP",
        astronaut_id="AST-001",
        session_id="SESSION-001",
        modality=InputModality.MULTIMODAL,
        input_data=AstronautInput(sensor_manifest_path=str(manifest_path))
    )

    runner = SupervisorWorkflowRunner()
    result = runner.run_pipeline(request=request)

    reg = result.get("evidence_registry") or []
    resp_item = next((item for item in reg if item.get("evidence_id") == "EV-PHY-RESP-RATE"), None)
    assert resp_item is None
    cov = (result.get("risk_assessment_result") or {}).get("coverage") or {}
    assert "RESPIRATORY" not in cov.get("evaluated_domains", [])

def test_04_missing_emg_telemetry_stream(tmp_path):
    """Verify that omitting EMG keeps musculoskeletal domain strictly unevaluated."""
    raw_manifest, _ = _load_base_manifest()
    manifest_no_emg = copy.deepcopy(raw_manifest)
    manifest_no_emg["signals"].pop("EMG", None)

    manifest_path = tmp_path / "manifest_no_emg.json"
    with open(manifest_path, "w", encoding="utf-8") as f:
        json.dump(manifest_no_emg, f)

    request = SupervisorRequest(
        request_id="REQ-STRESS-01-EMG",
        astronaut_id="AST-001",
        session_id="SESSION-001",
        modality=InputModality.MULTIMODAL,
        input_data=AstronautInput(sensor_manifest_path=str(manifest_path))
    )

    runner = SupervisorWorkflowRunner()
    result = runner.run_pipeline(request=request)

    cov = (result.get("risk_assessment_result") or {}).get("coverage") or {}
    assert "MUSCULOSKELETAL" in cov.get("unevaluated_domains", [])

def test_05_missing_acc_telemetry_stream(tmp_path):
    """Verify that omitting ACC removes physical activity contextual tracking."""
    raw_manifest, _ = _load_base_manifest()
    manifest_no_acc = copy.deepcopy(raw_manifest)
    manifest_no_acc["signals"].pop("ACC", None)

    manifest_path = tmp_path / "manifest_no_acc.json"
    with open(manifest_path, "w", encoding="utf-8") as f:
        json.dump(manifest_no_acc, f)

    request = SupervisorRequest(
        request_id="REQ-STRESS-01-ACC",
        astronaut_id="AST-001",
        session_id="SESSION-001",
        modality=InputModality.MULTIMODAL,
        input_data=AstronautInput(sensor_manifest_path=str(manifest_path))
    )

    runner = SupervisorWorkflowRunner()
    result = runner.run_pipeline(request=request)
    assert result.get("workflow_status") in ("COMPLETED", "PARTIALLY_COMPLETED")

def test_06_missing_temp_telemetry_stream(tmp_path):
    """Verify that omitting TEMP leaves thermoregulatory domain unevaluated."""
    raw_manifest, _ = _load_base_manifest()
    manifest_no_temp = copy.deepcopy(raw_manifest)
    manifest_no_temp["signals"].pop("TEMP", None)

    manifest_path = tmp_path / "manifest_no_temp.json"
    with open(manifest_path, "w", encoding="utf-8") as f:
        json.dump(manifest_no_temp, f)

    request = SupervisorRequest(
        request_id="REQ-STRESS-01-TEMP",
        astronaut_id="AST-001",
        session_id="SESSION-001",
        modality=InputModality.MULTIMODAL,
        input_data=AstronautInput(sensor_manifest_path=str(manifest_path))
    )

    runner = SupervisorWorkflowRunner()
    result = runner.run_pipeline(request=request)

    cov = (result.get("risk_assessment_result") or {}).get("coverage") or {}
    assert "THERMOREGULATORY" not in cov.get("evaluated_domains", [])

def test_07_multiple_sensors_missing_simultaneously(tmp_path):
    """Verify that multi-sensor omission severely reduces coverage and maintains INSUFFICIENT_DATA."""
    raw_manifest, _ = _load_base_manifest()
    manifest_multi = copy.deepcopy(raw_manifest)
    manifest_multi["signals"].pop("ECG", None)
    manifest_multi["signals"].pop("RESP", None)
    manifest_multi["signals"].pop("EMG", None)

    manifest_path = tmp_path / "manifest_multi_missing.json"
    with open(manifest_path, "w", encoding="utf-8") as f:
        json.dump(manifest_multi, f)

    request = SupervisorRequest(
        request_id="REQ-STRESS-01-MULTI",
        astronaut_id="AST-001",
        session_id="SESSION-001",
        modality=InputModality.MULTIMODAL,
        input_data=AstronautInput(sensor_manifest_path=str(manifest_path))
    )

    runner = SupervisorWorkflowRunner()
    result = runner.run_pipeline(request=request)

    assert result.get("overall_risk") in ("INSUFFICIENT_DATA", "UNKNOWN")
    cov = (result.get("risk_assessment_result") or {}).get("coverage") or {}
    ratio = cov.get("domain_coverage_ratio", 1.0)
    assert ratio <= 0.3

def test_08_all_sensors_missing_complete_telemetry_blackout(tmp_path):
    """Verify that total telemetry omission safely yields INSUFFICIENT_DATA without fabricating health."""
    raw_manifest, _ = _load_base_manifest()
    manifest_empty = copy.deepcopy(raw_manifest)
    manifest_empty["signals"] = {}

    manifest_path = tmp_path / "manifest_empty.json"
    with open(manifest_path, "w", encoding="utf-8") as f:
        json.dump(manifest_empty, f)

    request = SupervisorRequest(
        request_id="REQ-STRESS-01-BLACKOUT",
        astronaut_id="AST-001",
        session_id="SESSION-001",
        modality=InputModality.MULTIMODAL,
        input_data=AstronautInput(sensor_manifest_path=str(manifest_path))
    )

    runner = SupervisorWorkflowRunner()
    result = runner.run_pipeline(request=request)

    assert result.get("overall_risk") in ("INSUFFICIENT_DATA", "UNKNOWN")
    assert result.get("workflow_status") in ("COMPLETED", "PARTIALLY_COMPLETED")
    resp_text = result.get("final_response", "")
    assert "status is unknown, not that health is confirmed nominal" in resp_text
