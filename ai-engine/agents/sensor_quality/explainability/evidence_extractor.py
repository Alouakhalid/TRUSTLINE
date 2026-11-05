"""Evidence extractor utility for structuring diagnostic findings."""
from typing import Dict, Any, Optional
from ..schemas.output_schema import IssueEvidence

class EvidenceExtractor:
    """Helper for constructing standardized, empirical evidence records."""

    @staticmethod
    def build_evidence(
        metric_name: str,
        measured_value: float,
        threshold_value: float,
        units: Optional[str] = None,
        confidence: float = 1.0,
        context: Optional[Dict[str, Any]] = None
    ) -> IssueEvidence:
        return IssueEvidence(
            metric_name=metric_name,
            measured_value=float(measured_value),
            threshold_value=float(threshold_value),
            units=units,
            confidence=max(0.0, min(1.0, float(confidence))),
            additional_context=context or {}
        )
