"""RLHF Feedback Collection & Expert Review Subsystem.

This package provides data schemas and storage infrastructure for capturing
expert human-in-the-loop evaluations (Flight Surgeons, Biomedical Engineers,
Auditors) of agent-generated responses.

IMPORTANT:
Capturing reviews does NOT continuously retrain or alter model weights at runtime.
"""

from RLHF.schemas import (
    FeedbackRecord,
    FeedbackSource,
    ReviewerDecision,
)
from RLHF.feedback_collector import FeedbackCollector

__all__ = [
    "FeedbackRecord",
    "FeedbackSource",
    "ReviewerDecision",
    "FeedbackCollector",
]
