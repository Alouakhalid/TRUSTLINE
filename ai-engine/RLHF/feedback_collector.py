"""Thread-safe RLHF Feedback Collector for TRUSTLINE.

This module provides persistent capture, querying, and offline export
of human-in-the-loop expert evaluations across TRUSTLINE agents.

DESIGN PRINCIPLE:
This subsystem operates strictly out-of-band. Capturing approvals,
rejections, edits, or clinical flags does NOT modify hosted model weights
or trigger automated retraining pipelines during mission operations.
All collected data is stored for safety audits, clinical oversight,
and offline research curation.
"""

import json
import os
import sqlite3
import threading
from typing import Any, Dict, List, Optional

from RLHF.schemas import FeedbackRecord, FeedbackSource, ReviewerDecision


class FeedbackCollector:
    """Thread-safe collector and repository for RLHF expert reviews.

    Uses SQLite for persistent storage with JSON serialization of
    complex nested structures (evidence references, metadata).
    """

    def __init__(self, db_path: str = "data/rlhf_feedback.db") -> None:
        """Initialize the feedback collector with a SQLite database.

        Args:
            db_path: Path to the SQLite database file or ':memory:' for transient tests.
        """
        self.db_path = db_path
        self._lock = threading.Lock()
        self._persistent_conn: Optional[sqlite3.Connection] = None

        if db_path != ":memory:":
            os.makedirs(os.path.dirname(os.path.abspath(db_path)), exist_ok=True)
        else:
            self._persistent_conn = sqlite3.connect(":memory:", check_same_thread=False)
            self._persistent_conn.row_factory = sqlite3.Row

        self._init_db()

    def _get_connection(self) -> sqlite3.Connection:
        """Create or return a SQLite connection with row factory."""
        if self._persistent_conn is not None:
            return self._persistent_conn
        conn = sqlite3.connect(self.db_path, check_same_thread=False)
        conn.row_factory = sqlite3.Row
        return conn

    def _close_connection(self, conn: sqlite3.Connection) -> None:
        """Close connection unless it is a persistent in-memory connection."""
        if self._persistent_conn is None:
            conn.close()

    def _init_db(self) -> None:
        """Initialize the feedback database table if it does not exist."""
        with self._lock:
            conn = self._get_connection()
            try:
                cursor = conn.cursor()
                cursor.execute(
                    """
                    CREATE TABLE IF NOT EXISTS rlhf_feedback (
                        feedback_id TEXT PRIMARY KEY,
                        agent_id TEXT NOT NULL,
                        model_id TEXT NOT NULL,
                        model_revision TEXT,
                        prompt_id TEXT,
                        prompt_text TEXT NOT NULL,
                        response_id TEXT,
                        response_text TEXT NOT NULL,
                        edited_response_text TEXT,
                        evidence_references TEXT,
                        reviewer_decision TEXT NOT NULL,
                        review_notes TEXT,
                        feedback_source TEXT NOT NULL,
                        timestamp_utc TEXT NOT NULL,
                        metadata_json TEXT
                    )
                    """
                )
                cursor.execute(
                    """
                    CREATE INDEX IF NOT EXISTS idx_agent_decision
                    ON rlhf_feedback (agent_id, reviewer_decision)
                    """
                )
                conn.commit()
            finally:
                self._close_connection(conn)

    def record_feedback(self, record: FeedbackRecord) -> str:
        """Persist a feedback record into the database.

        Args:
            record: FeedbackRecord instance to persist.

        Returns:
            The feedback_id of the recorded entry.
        """
        with self._lock:
            conn = self._get_connection()
            try:
                cursor = conn.cursor()
                cursor.execute(
                    """
                    INSERT INTO rlhf_feedback (
                        feedback_id, agent_id, model_id, model_revision,
                        prompt_id, prompt_text, response_id, response_text,
                        edited_response_text, evidence_references,
                        reviewer_decision, review_notes, feedback_source,
                        timestamp_utc, metadata_json
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        record.feedback_id,
                        record.agent_id,
                        record.model_id,
                        record.model_revision,
                        record.prompt_id,
                        record.prompt_text,
                        record.response_id,
                        record.response_text,
                        record.edited_response_text,
                        json.dumps(record.evidence_references),
                        record.reviewer_decision.value,
                        record.review_notes,
                        record.feedback_source.value,
                        record.timestamp_utc,
                        json.dumps(record.metadata),
                    ),
                )
                conn.commit()
                return record.feedback_id
            finally:
                self._close_connection(conn)

    def get_feedback(self, feedback_id: str) -> Optional[FeedbackRecord]:
        """Retrieve a single feedback record by its unique ID.

        Args:
            feedback_id: Unique identifier.

        Returns:
            FeedbackRecord if found, otherwise None.
        """
        with self._lock:
            conn = self._get_connection()
            try:
                cursor = conn.cursor()
                cursor.execute(
                    "SELECT * FROM rlhf_feedback WHERE feedback_id = ?",
                    (feedback_id,),
                )
                row = cursor.fetchone()
                if not row:
                    return None
                return self._row_to_record(row)
            finally:
                self._close_connection(conn)

    def query_feedback(
        self,
        agent_id: Optional[str] = None,
        decision: Optional[ReviewerDecision] = None,
        limit: int = 100,
    ) -> List[FeedbackRecord]:
        """Query feedback records by agent and/or reviewer decision.

        Args:
            agent_id: Optional agent identifier filter.
            decision: Optional ReviewerDecision filter.
            limit: Maximum records to return.

        Returns:
            List of matching FeedbackRecord instances.
        """
        query = "SELECT * FROM rlhf_feedback WHERE 1=1"
        params: List[Any] = []

        if agent_id:
            query += " AND agent_id = ?"
            params.append(agent_id)
        if decision:
            query += " AND reviewer_decision = ?"
            params.append(decision.value)

        query += " ORDER BY timestamp_utc DESC LIMIT ?"
        params.append(limit)

        with self._lock:
            conn = self._get_connection()
            try:
                cursor = conn.cursor()
                cursor.execute(query, tuple(params))
                rows = cursor.fetchall()
                return [self._row_to_record(r) for r in rows]
            finally:
                self._close_connection(conn)

    def export_for_alignment_analysis(self, output_filepath: str) -> int:
        """Export all feedback records as JSON Lines for offline analysis.

        Args:
            output_filepath: Filepath where JSONL lines will be written.

        Returns:
            The number of records exported.
        """
        records = self.query_feedback(limit=100000)
        os.makedirs(os.path.dirname(os.path.abspath(output_filepath)), exist_ok=True)
        with open(output_filepath, "w", encoding="utf-8") as f:
            for rec in records:
                f.write(rec.model_dump_json() + "\n")
        return len(records)

    def get_statistics(self) -> Dict[str, Any]:
        """Compute summary statistics of collected feedback.

        Returns:
            Dict containing total counts, counts by decision, and counts by agent.
        """
        with self._lock:
            conn = self._get_connection()
            try:
                cursor = conn.cursor()
                cursor.execute("SELECT COUNT(*) as total FROM rlhf_feedback")
                total = cursor.fetchone()["total"]

                cursor.execute(
                    "SELECT reviewer_decision, COUNT(*) as count "
                    "FROM rlhf_feedback GROUP BY reviewer_decision"
                )
                by_decision = {
                    row["reviewer_decision"]: row["count"] for row in cursor.fetchall()
                }

                cursor.execute(
                    "SELECT agent_id, COUNT(*) as count "
                    "FROM rlhf_feedback GROUP BY agent_id"
                )
                by_agent = {row["agent_id"]: row["count"] for row in cursor.fetchall()}

                return {
                    "total_records": total,
                    "by_decision": by_decision,
                    "by_agent": by_agent,
                }
            finally:
                self._close_connection(conn)

    def _row_to_record(self, row: sqlite3.Row) -> FeedbackRecord:
        """Convert a database row to a FeedbackRecord instance."""
        evidence_raw = row["evidence_references"]
        evidence_list = json.loads(evidence_raw) if evidence_raw else []

        metadata_raw = row["metadata_json"]
        metadata_dict = json.loads(metadata_raw) if metadata_raw else {}

        return FeedbackRecord(
            feedback_id=row["feedback_id"],
            agent_id=row["agent_id"],
            model_id=row["model_id"],
            model_revision=row["model_revision"],
            prompt_id=row["prompt_id"],
            prompt_text=row["prompt_text"],
            response_id=row["response_id"],
            response_text=row["response_text"],
            edited_response_text=row["edited_response_text"],
            evidence_references=evidence_list,
            reviewer_decision=ReviewerDecision(row["reviewer_decision"]),
            review_notes=row["review_notes"],
            feedback_source=FeedbackSource(row["feedback_source"]),
            timestamp_utc=row["timestamp_utc"],
            metadata=metadata_dict,
        )
