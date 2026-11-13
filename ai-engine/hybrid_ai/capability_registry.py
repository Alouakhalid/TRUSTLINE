"""
Capability and Safety Registry defining routing policies and clinical safety boundaries.
"""
from typing import Dict
from .schemas import TaskCategory, RoutingPolicy

TASK_POLICY_MATRIX: Dict[TaskCategory, RoutingPolicy] = {
    TaskCategory.GENERAL_EXPLANATION: RoutingPolicy.LOCAL_ELIGIBLE,
    TaskCategory.CONCISE_SUMMARIZATION: RoutingPolicy.LOCAL_ELIGIBLE,
    TaskCategory.STRUCTURED_EXTRACTION: RoutingPolicy.LOCAL_ELIGIBLE,
    TaskCategory.AGENT_REPORT_FORMATTING: RoutingPolicy.LOCAL_ELIGIBLE,
    TaskCategory.MEDICAL_DOCUMENT_OCR: RoutingPolicy.CLOUD_ONLY,
    TaskCategory.MEDICAL_RAG_SYNTHESIS: RoutingPolicy.LOCAL_ELIGIBLE,
    TaskCategory.PERSONAL_HEALTH_SYNTHESIS: RoutingPolicy.LOCAL_ELIGIBLE,
    TaskCategory.RISK_ASSESSMENT_SYNTHESIS: RoutingPolicy.LOCAL_ELIGIBLE,
    TaskCategory.TOOL_CALLING: RoutingPolicy.UNAVAILABLE,
    TaskCategory.VOICE_INTERPRETATION: RoutingPolicy.CLOUD_ONLY,
    TaskCategory.SENSOR_QUALITY_BRIEFING: RoutingPolicy.LOCAL_ELIGIBLE,
    TaskCategory.SUPERVISOR_FINAL_REPORT: RoutingPolicy.DETERMINISTIC_OFFLINE
}

class CapabilityRegistry:
    """Evaluates task eligibility against safety constraints and provider capabilities."""

    @classmethod
    def get_policy(cls, task_category: TaskCategory) -> RoutingPolicy:
        """Return the routing policy associated with a task category."""
        return TASK_POLICY_MATRIX.get(task_category, RoutingPolicy.UNAVAILABLE)

    @classmethod
    def is_local_eligible(cls, task_category: TaskCategory) -> bool:
        """Determine whether a task may fallback to local edge inference."""
        return cls.get_policy(task_category) == RoutingPolicy.LOCAL_ELIGIBLE

    @classmethod
    def is_cloud_only(cls, task_category: TaskCategory) -> bool:
        """Determine whether a task strictly requires cloud capabilities (e.g. Vision OCR, Audio)."""
        return cls.get_policy(task_category) == RoutingPolicy.CLOUD_ONLY

    @classmethod
    def is_deterministic_offline(cls, task_category: TaskCategory) -> bool:
        """Determine whether a task must be satisfied deterministically without LLMs."""
        return cls.get_policy(task_category) == RoutingPolicy.DETERMINISTIC_OFFLINE
