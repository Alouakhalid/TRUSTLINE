"""Schemas for the TRUSTLINE RLHF Feedback Collection Subsystem.

This module defines data structures for human-in-the-loop and expert feedback
capture. Records captured through this system are logged for offline analysis,
compliance auditing, and future fine-tuning dataset curation.

IMPORTANT NOTE:
Capturing feedback through this subsystem does NOT alter hosted model weights,
nor does it trigger dynamic or online retraining of the active inference model.
"""

from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, List, Optional
import uuid
from pydantic import BaseModel, Field


class ReviewerDecision(str, Enum):
    """Reviewer decision categories for human feedback."""
    APPROVED = "APPROVED"
    REJECTED = "REJECTED"
    EDITED = "EDITED"
    FLAGGED_EXPERT_REVIEW = "FLAGGED_EXPERT_REVIEW"


class FeedbackSource(str, Enum):
    """Authorized roles capable of submitting feedback."""
    FLIGHT_SURGEON = "FLIGHT_SURGEON"
    BIOMEDICAL_ENGINEER = "BIOMEDICAL_ENGINEER"
    AUTOMATED_AUDITOR = "AUTOMATED_AUDITOR"
    SAFETY_OFFICER = "SAFETY_OFFICER"


class FeedbackRecord(BaseModel):
    """A standardized record capturing reviewer feedback on LLM generation.

    Attributes:
        feedback_id: Unique identifier for the feedback entry.
        agent_id: Identifier of the agent originating the prompt/response.
        model_id: Identifier of the model that generated the response.
        model_revision: Optional revision or commit hash of the model.
        prompt_id: Optional tracking identifier for the prompt.
        prompt_text: Full prompt or context provided to the model.
        response_id: Optional tracking identifier for the response.
        response_text: Full generated response text.
        edited_response_text: Expert-corrected or revised response text if edited.
        evidence_references: List of cited evidence IDs or telemetry keys.
        reviewer_decision: Decision (APPROVED, REJECTED, EDITED, FLAGGED).
        review_notes: Contextual notes or clinical rationale provided by reviewer.
        feedback_source: Role of the reviewer submitting feedback.
        timestamp_utc: ISO 8601 UTC timestamp of feedback submission.
        metadata: Arbitrary additional metadata for auditing or telemetry.
    """
    feedback_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    agent_id: str
    model_id: str
    model_revision: Optional[str] = None
    prompt_id: Optional[str] = None
    prompt_text: str
    response_id: Optional[str] = None
    response_text: str
    edited_response_text: Optional[str] = None
    evidence_references: List[str] = Field(default_factory=list)
    reviewer_decision: ReviewerDecision
    review_notes: Optional[str] = None
    feedback_source: FeedbackSource
    timestamp_utc: str = Field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat()
    )
    metadata: Dict[str, Any] = Field(default_factory=dict)
