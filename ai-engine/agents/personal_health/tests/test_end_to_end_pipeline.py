"""Integration test executing complete Personal Health Agent pipeline."""
import json
import tempfile
from pathlib import Path
import pytest
from personal_health.main import run_personal_health_pipeline
from personal_health.schemas.assessment import PersonalHealthAssessment

def test_full_personal_health_pipeline():
    """Verify execution of pipeline against real sensor quality report and manifest."""
    root = Path(__file__).resolve().parent.parent.parent
    manifest = root / "sensor_quality" / "data" / "input" / "astronaut_health_data.json"
    report = root / "sensor_quality" / "data" / "output" / "sensor_quality_report.json"

    with tempfile.TemporaryDirectory() as tmp_dir:
        rc = run_personal_health_pipeline(
            manifest_path=str(manifest),
            quality_report_path=str(report),
            symptom_text="Mild head fullness consistent with microgravity adaptation",
            run_crew=False,
            output_dir=tmp_dir
        )
        assert rc == 0
        out_json = Path(tmp_dir) / "personal_health_assessment.json"
        assert out_json.exists()

        with open(out_json, "r", encoding="utf-8") as f:
            data = json.load(f)

        assessment = PersonalHealthAssessment(**data)
        assert assessment.astronaut_id == "AST-001"
        assert assessment.session_id == "SESSION-001"
        assert assessment.assessment_status.value in ("COMPLETED", "URGENT_ESCALATION", "REQUIRES_CLARIFICATION")
        assert assessment.baseline_status.value == "not_available"
        assert assessment.core_features is not None
        assert len(assessment.ml_findings) >= 1
        assert assessment.next_agent == "risk_assessment_agent"
