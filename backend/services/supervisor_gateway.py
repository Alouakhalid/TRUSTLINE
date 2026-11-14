"""Gateway adapter to the existing LangGraph Supervisor (the sole orchestrator).

This module adds NO orchestration logic. It converts an authorized API request
into a ``SupervisorRequest`` for the existing 10-node workflow and reports the
actual outcome:

- Provider routing at the API boundary defaults to ``LOCAL_ONLY`` (Ollama if
  available, otherwise the existing deterministic fallback) so that a chat
  reply never stalls on misconfigured or unbillable cloud providers. Operators
  can re-enable cloud paths with ``TRUSTLINE_AI_ROUTER_MODE=HYBRID``.
- The reported provider/agent statuses are exactly what the workflow produced.
- If the supervisor stack cannot be imported or the invocation fails, the
  gateway returns a truthful error state; nothing is invented.
"""
from __future__ import annotations

import os
import threading
import time
from typing import Any

from backend.services.integrations import import_attribute

_LOCK = threading.Lock()
_runner: Any = None
_import_error: str | None = None


def _apply_router_mode() -> None:
    """Default the API-boundary router mode before the hybrid stack is imported."""
    os.environ.setdefault("AI_ROUTER_MODE", os.getenv("TRUSTLINE_AI_ROUTER_MODE", "LOCAL_ONLY"))


def _get_runner() -> Any:
    global _runner, _import_error
    if _runner is not None:
        return _runner
    with _LOCK:
        if _runner is not None:
            return _runner
        _apply_router_mode()
        try:
            runner_cls = import_attribute("agents.supervisor.workflow.graph", "SupervisorWorkflowRunner")
            request_cls = import_attribute("agents.supervisor.schemas.requests", "SupervisorRequest")
            modality = import_attribute("agents.supervisor.schemas.requests", "InputModality")
            _runner = {"runner": runner_cls(), "request_cls": request_cls, "modality": modality}
        except Exception as exc:  # truthful unavailability, never a stub success
            _import_error = f"{type(exc).__name__}: {exc}"
            raise
    return _runner


def is_available() -> bool:
    try:
        _get_runner()
        return True
    except Exception:
        return False


def unavailability_reason() -> str | None:
    try:
        _get_runner()
    except Exception:
        return _import_error
    return None


def run_text_assessment(
    astronaut_id: str,
    session_id: str,
    text_query: str,
    mission_context: dict[str, Any] | None = None,
    request_id: str | None = None,
    document_paths: list[str] | None = None,
) -> dict[str, Any]:
    """Run the real Supervisor workflow for a text query and optional medical documents and report the outcome."""
    bundle = _get_runner()
    request_cls, modality = bundle["request_cls"], bundle["modality"]
    input_data: dict[str, Any] = {
        "text_query": text_query,
        "mission_context": mission_context or {},
    }
    if document_paths:
        input_data["document_paths"] = document_paths

    request = request_cls(
        request_id=request_id or f"API-{int(time.time() * 1000)}",
        astronaut_id=astronaut_id,
        session_id=session_id,
        modality=modality.DOCUMENT if document_paths else modality.TEXT,
        input_data=input_data,
        request_metadata={"gateway": "backend/api", "router_mode": os.environ.get("AI_ROUTER_MODE", "LOCAL_ONLY")},
    )
    started = time.perf_counter()
    try:
        state = bundle["runner"].run_pipeline(request=request)
    except Exception as exc:
        return {
            "provider_status": "SUPERVISOR_FAILED",
            "error": f"{type(exc).__name__}: {exc}",
            "duration_ms": round((time.perf_counter() - started) * 1000, 1),
            "final_assessment": None,
        }
    assessment = state.get("final_assessment") or {}
    statuses = assessment.get("agent_execution_statuses") or {}
    return {
        "provider_status": "SUPERVISOR_COMPLETED",
        "duration_ms": round((time.perf_counter() - started) * 1000, 1),
        "router_mode": os.environ.get("AI_ROUTER_MODE", "LOCAL_ONLY"),
        "workflow_id": assessment.get("workflow_id"),
        "completion_status": str(assessment.get("workflow_completion_status", "")),
        "overall_risk": assessment.get("overall_risk"),
        "overall_confidence": assessment.get("overall_confidence"),
        "astronaut_facing_response": assessment.get("astronaut_facing_response", ""),
        "executive_synthesis": assessment.get("executive_synthesis"),
        "medical_documents": state.get("medical_documents") or [],
        "pending_medical_records": state.get("pending_medical_records") or [],
        "confirmed_medical_records": state.get("confirmed_medical_records") or [],
        "agent_statuses": {
            name: {
                "status": str((info or {}).get("status", "")),
                "execution_time_ms": (info or {}).get("execution_time_ms"),
                "warnings": (info or {}).get("warnings", []),
            }
            for name, info in statuses.items()
        },
        "evidence_references": [
            {
                "evidence_id": item.get("evidence_id"),
                "source_agent": item.get("source_agent"),
                "domain": item.get("domain"),
                "metric_name": item.get("metric_name"),
                "observed_value": item.get("observed_value"),
                "validity_status": item.get("validity_status"),
                "is_quarantined": item.get("is_quarantined", False),
                "provenance": item.get("provenance"),
            }
            for item in (assessment.get("evidence_references") or [])
        ],
        "missing_information": assessment.get("missing_information", []),
        "recommended_actions": assessment.get("recommended_actions", []),
        "escalation_required": assessment.get("escalation_required", False),
    }
