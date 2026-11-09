"""Stress Test 08: Persistence failures, database resilience, duplicate execution, and recovery."""
import json
import sqlite3
import pytest
from pathlib import Path
from unittest.mock import patch
from supervisor.services.persistence_service import PersistenceService
from supervisor.config.settings import get_supervisor_settings
from supervisor.workflow.nodes import persistence_node

def test_01_sqlite_unavailable_records_warning_without_crash(tmp_path):
    """Verify database connection failure generates warning and does not crash persistence."""
    cfg = get_supervisor_settings()
    orig_url = cfg.database_url
    try:
        cfg.database_url = "sqlite:////non_existent_mount/invalid_dir/forbidden.db"
        assessment = {
            "assessment_id": "SUP-TEST-PERSIST-01",
            "astronaut_id": "AST-001",
            "session_id": "SESSION-001",
            "workflow_id": "WF-P-01"
        }
        success, filepath, warnings = PersistenceService.save_final_assessment(assessment)
        assert any("database persistence failed" in w.lower() for w in warnings)
    finally:
        cfg.database_url = orig_url

def test_02_json_write_failure_handled_safely(tmp_path):
    """Verify file write errors are captured as warnings."""
    cfg = get_supervisor_settings()
    orig_dir = cfg.output_dir
    try:
        cfg.output_dir = Path("/forbidden_system_root/read_only_output")
        assessment = {
            "assessment_id": "SUP-TEST-PERSIST-02",
            "astronaut_id": "AST-001",
            "session_id": "SESSION-001",
            "workflow_id": "WF-P-02"
        }
        success, filepath, warnings = PersistenceService.save_final_assessment(assessment)
        assert any("Failed to write assessment JSON" in w for w in warnings)
    finally:
        cfg.output_dir = orig_dir

def test_03_persistence_failure_degrades_workflow_completion_status(tmp_path):
    """Verify persistence failure flags error in state and prevents unqualified COMPLETED status."""
    state = {
        "final_assessment": {
            "assessment_id": "SUP-P03",
            "astronaut_id": "AST-001",
            "session_id": "SESSION-001",
            "workflow_id": "WF-P03",
            "workflow_completion_status": "COMPLETED"
        },
        "workflow_status": "COMPLETED",
        "warnings": []
    }
    with patch("supervisor.services.persistence_service.PersistenceService.save_final_assessment", return_value=(False, "", ["Disk full error"])):
        updates = persistence_node(state)

    assert "errors" in updates
    assert any("Persistence Failure" in e for e in updates["errors"])
    assert updates["workflow_status"] != "COMPLETED"

def test_04_duplicate_workflow_execution_idempotency(tmp_path):
    """Verify executing persistence twice with same assessment_id updates existing row instead of corrupting db."""
    cfg = get_supervisor_settings()
    orig_url = cfg.database_url
    orig_dir = cfg.output_dir
    try:
        test_db = tmp_path / "test_trustline.db"
        cfg.database_url = f"sqlite:///{test_db}"
        cfg.output_dir = tmp_path

        assessment = {
            "assessment_id": "SUP-IDEMPOTENT-01",
            "astronaut_id": "AST-001",
            "session_id": "SESSION-001",
            "workflow_id": "WF-IDEM-01",
            "workflow_completion_status": "PARTIALLY_COMPLETED",
            "overall_risk": "INSUFFICIENT_DATA",
            "escalation_state": "NO_TRIGGER_DETECTED",
            "generation_timestamp": "2026-11-09T00:00:00"
        }

        success1, _, _ = PersistenceService.save_final_assessment(assessment)
        assert success1 is True

        assessment["overall_risk"] = "INSUFFICIENT_DATA"
        success2, _, _ = PersistenceService.save_final_assessment(assessment)
        assert success2 is True

        conn = sqlite3.connect(str(test_db))
        cursor = conn.cursor()
        cursor.execute("SELECT COUNT(*) FROM supervisor_assessments WHERE assessment_id = 'SUP-IDEMPOTENT-01'")
        count = cursor.fetchone()[0]
        conn.close()

        assert count == 1
    finally:
        cfg.database_url = orig_url
        cfg.output_dir = orig_dir
