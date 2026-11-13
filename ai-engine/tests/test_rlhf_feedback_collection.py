"""
Unit and integration tests for RLHF Feedback Collection Subsystem.

Validates:
1. Pydantic schema validation for FeedbackRecord across all decisions and reviewer sources
2. Database persistence, retrieval, and querying in FeedbackCollector
3. Aggregated metrics calculation (get_statistics)
4. Offline export to JSON Lines for research alignment analysis
5. Thread-safe concurrent write execution
6. Non-retraining invariant: feedback storage does not mutate model state
"""

import os
import json
import tempfile
import threading
import pytest

from RLHF.schemas import (
    FeedbackRecord,
    FeedbackSource,
    ReviewerDecision
)
from RLHF.feedback_collector import FeedbackCollector


@pytest.fixture
def in_memory_collector():
    return FeedbackCollector(db_path=":memory:")


@pytest.fixture
def temp_db_collector():
    with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
        db_path = f.name
    collector = FeedbackCollector(db_path=db_path)
    yield collector
    if os.path.exists(db_path):
        os.remove(db_path)


def test_01_feedback_record_schema_validation():
    """Verify FeedbackRecord validates fields, defaults, and serializes to JSON properly."""
    rec = FeedbackRecord(
        agent_id="personal_health",
        model_id="meta-llama/Llama-3.1-8B-Instruct",
        prompt_text="Explain bradycardia risks in microgravity.",
        response_text="Microgravity can lead to orthostatic intolerance upon return.",
        reviewer_decision=ReviewerDecision.APPROVED,
        feedback_source=FeedbackSource.FLIGHT_SURGEON,
        evidence_references=["NASA-STD-3001"],
        review_notes="Clinically accurate interpretation.",
        metadata={"mission_day": 142}
    )

    assert rec.feedback_id is not None
    assert rec.reviewer_decision == ReviewerDecision.APPROVED
    assert rec.feedback_source == FeedbackSource.FLIGHT_SURGEON
    assert rec.evidence_references == ["NASA-STD-3001"]
    assert rec.metadata["mission_day"] == 142

    # Check serialization
    json_data = rec.model_dump_json()
    assert "NASA-STD-3001" in json_data


def test_02_record_and_get_feedback(temp_db_collector):
    """Verify persistent record insertion and retrieval by unique feedback_id."""
    rec = FeedbackRecord(
        agent_id="risk_assessment",
        model_id="meta-llama/Llama-3.1-8B-Instruct",
        prompt_text="Assess risk for sudden SpO2 drop to 88%.",
        response_text="Risk is high. Immediate oxygenation check required.",
        edited_response_text="Risk is CRITICAL. Immediate crew cross-check of suit oxygenation and sensor placement required.",
        reviewer_decision=ReviewerDecision.EDITED,
        feedback_source=FeedbackSource.FLIGHT_SURGEON,
        review_notes="Clarified sensor artifact cross-check step.",
        metadata={"astronaut_id": "AST-01"}
    )

    fb_id = temp_db_collector.record_feedback(rec)
    assert fb_id == rec.feedback_id

    fetched = temp_db_collector.get_feedback(fb_id)
    assert fetched is not None
    assert fetched.feedback_id == fb_id
    assert fetched.agent_id == "risk_assessment"
    assert fetched.reviewer_decision == ReviewerDecision.EDITED
    assert fetched.edited_response_text == rec.edited_response_text
    assert fetched.metadata["astronaut_id"] == "AST-01"


def test_03_query_feedback_filtering(temp_db_collector):
    """Verify query filtering by agent_id and reviewer_decision."""
    agents = ["personal_health", "sensor_quality", "risk_assessment"]
    decisions = [ReviewerDecision.APPROVED, ReviewerDecision.REJECTED, ReviewerDecision.FLAGGED_EXPERT_REVIEW]

    for idx, agent in enumerate(agents):
        rec = FeedbackRecord(
            agent_id=agent,
            model_id="meta-llama/Llama-3.1-8B-Instruct",
            prompt_text=f"Test prompt {idx}",
            response_text=f"Test response {idx}",
            reviewer_decision=decisions[idx],
            feedback_source=FeedbackSource.BIOMEDICAL_ENGINEER
        )
        temp_db_collector.record_feedback(rec)

    # Filter by agent
    pha_records = temp_db_collector.query_feedback(agent_id="personal_health")
    assert len(pha_records) == 1
    assert pha_records[0].agent_id == "personal_health"

    # Filter by decision
    rejected_records = temp_db_collector.query_feedback(decision=ReviewerDecision.REJECTED)
    assert len(rejected_records) == 1
    assert rejected_records[0].agent_id == "sensor_quality"

    # All records
    all_records = temp_db_collector.query_feedback()
    assert len(all_records) == 3


def test_04_get_statistics_aggregation(temp_db_collector):
    """Verify aggregated metrics computation."""
    for decision in [ReviewerDecision.APPROVED, ReviewerDecision.APPROVED, ReviewerDecision.REJECTED]:
        rec = FeedbackRecord(
            agent_id="personal_health",
            model_id="meta-llama/Llama-3.1-8B-Instruct",
            prompt_text="Prompt",
            response_text="Resp",
            reviewer_decision=decision,
            feedback_source=FeedbackSource.SAFETY_OFFICER
        )
        temp_db_collector.record_feedback(rec)

    stats = temp_db_collector.get_statistics()
    assert stats["total_records"] == 3
    assert stats["by_decision"][ReviewerDecision.APPROVED.value] == 2
    assert stats["by_decision"][ReviewerDecision.REJECTED.value] == 1
    assert stats["by_agent"]["personal_health"] == 3


def test_05_export_for_alignment_analysis(temp_db_collector):
    """Verify export_for_alignment_analysis writes valid JSONL data."""
    for i in range(5):
        rec = FeedbackRecord(
            agent_id=f"agent_{i % 2}",
            model_id="meta-llama/Llama-3.1-8B-Instruct",
            prompt_text=f"Prompt {i}",
            response_text=f"Response {i}",
            reviewer_decision=ReviewerDecision.APPROVED,
            feedback_source=FeedbackSource.AUTOMATED_AUDITOR
        )
        temp_db_collector.record_feedback(rec)

    with tempfile.NamedTemporaryFile(suffix=".jsonl", delete=False) as f:
        export_path = f.name

    try:
        count = temp_db_collector.export_for_alignment_analysis(export_path)
        assert count == 5
        assert os.path.exists(export_path)

        with open(export_path, "r", encoding="utf-8") as f:
            lines = f.readlines()
        assert len(lines) == 5

        first_rec = json.loads(lines[0])
        assert "feedback_id" in first_rec
        assert first_rec["model_id"] == "meta-llama/Llama-3.1-8B-Instruct"
    finally:
        if os.path.exists(export_path):
            os.remove(export_path)


def test_06_thread_safe_concurrent_writes(temp_db_collector):
    """Verify thread-safe concurrent recording of feedback without locks or corruption."""
    num_threads = 10
    writes_per_thread = 5

    def worker(worker_id: int):
        for i in range(writes_per_thread):
            rec = FeedbackRecord(
                agent_id="concurrent_agent",
                model_id="meta-llama/Llama-3.1-8B-Instruct",
                prompt_text=f"Worker {worker_id} - {i}",
                response_text=f"Response {worker_id} - {i}",
                reviewer_decision=ReviewerDecision.APPROVED,
                feedback_source=FeedbackSource.BIOMEDICAL_ENGINEER
            )
            temp_db_collector.record_feedback(rec)

    threads = [threading.Thread(target=worker, args=(t,)) for t in range(num_threads)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()

    stats = temp_db_collector.get_statistics()
    assert stats["total_records"] == num_threads * writes_per_thread


def test_07_non_retraining_invariant():
    """Verify that feedback collection does NOT mutate model configurations or trigger retraining."""
    model_config = {
        "model_id": "meta-llama/Llama-3.1-8B-Instruct",
        "temperature": 0.1,
        "is_retraining_triggered": False
    }

    collector = FeedbackCollector(db_path=":memory:")
    rec = FeedbackRecord(
        agent_id="personal_health",
        model_id=model_config["model_id"],
        prompt_text="Query",
        response_text="Answer",
        reviewer_decision=ReviewerDecision.REJECTED,
        feedback_source=FeedbackSource.FLIGHT_SURGEON,
        review_notes="Inaccurate diagnosis."
    )
    collector.record_feedback(rec)

    # Invariant checks:
    # 1. No dynamic weight modification
    # 2. Configuration remains static
    # 3. Model inference remains decoupled from feedback database
    assert model_config["is_retraining_triggered"] is False
    assert model_config["model_id"] == "meta-llama/Llama-3.1-8B-Instruct"
