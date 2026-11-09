"""Persistence service saving final assessments to disk and edge database."""
import json
import sqlite3
from pathlib import Path
from typing import Dict, Any, Tuple
from ..config.settings import get_supervisor_settings

class PersistenceService:
    """Manages output serialization and local SQLite session persistence."""

    @classmethod
    def save_final_assessment(cls, assessment_dict: Dict[str, Any]) -> Tuple[bool, str, list]:
        """Write JSON output artifact and persist summary row into SQLite database."""
        cfg = get_supervisor_settings()
        warnings = []
        target_dir = cfg.output_dir
        json_file = target_dir / "final_supervisor_assessment.json"
        try:
            target_dir.mkdir(parents=True, exist_ok=True)
            with open(json_file, "w", encoding="utf-8") as f:
                json.dump(assessment_dict, f, indent=2, default=str)
        except Exception as exc:
            warnings.append(f"Failed to write assessment JSON to {json_file}: {str(exc)}")

        db_success = False
        try:
            db_path_str = cfg.database_url.replace("sqlite:///", "")
            db_path = Path(db_path_str).resolve()
            db_path.parent.mkdir(parents=True, exist_ok=True)
            conn = sqlite3.connect(str(db_path), timeout=5.0)
            cursor = conn.cursor()
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS supervisor_assessments (
                    assessment_id TEXT PRIMARY KEY,
                    astronaut_id TEXT NOT NULL,
                    session_id TEXT NOT NULL,
                    workflow_id TEXT NOT NULL,
                    completion_status TEXT NOT NULL,
                    overall_risk TEXT NOT NULL,
                    escalation_state TEXT NOT NULL,
                    generation_timestamp TEXT NOT NULL,
                    serialized_payload TEXT NOT NULL
                )
            """)
            cursor.execute("""
                INSERT OR REPLACE INTO supervisor_assessments (
                    assessment_id, astronaut_id, session_id, workflow_id,
                    completion_status, overall_risk, escalation_state,
                    generation_timestamp, serialized_payload
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                assessment_dict.get("assessment_id", "A-UNKNOWN"),
                assessment_dict.get("astronaut_id", "AST-UNKNOWN"),
                assessment_dict.get("session_id", "S-UNKNOWN"),
                assessment_dict.get("workflow_id", "WF-UNKNOWN"),
                str(assessment_dict.get("workflow_completion_status", "COMPLETED")),
                str(assessment_dict.get("overall_risk", "UNKNOWN")),
                str(assessment_dict.get("escalation_state", "UNKNOWN")),
                str(assessment_dict.get("generation_timestamp", "")),
                json.dumps(assessment_dict, default=str)
            ))
            conn.commit()
            conn.close()
            db_success = True
        except Exception as exc:
            warnings.append(f"Edge database persistence failed: {str(exc)}")

        json_exists = False
        try:
            json_exists = json_file.exists()
        except Exception:
            json_exists = False

        return (json_exists or db_success), str(json_file), warnings
