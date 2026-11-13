"""
Structured, privacy-aware telemetry recording for Hybrid AI Router operations.
"""
from typing import Dict, Any, List, Optional
import uuid
import time
from datetime import datetime
from pydantic import BaseModel, Field

class RouterTelemetryRecord(BaseModel):
    """Audit entry recording request dispatch and outcome."""
    request_id: str
    timestamp_iso: str = Field(default_factory=lambda: datetime.utcnow().isoformat())
    task_category: str
    provider_selected: str
    model_selected: str
    routing_decision: str
    fallback_reason: Optional[str] = None
    latency_ms: float = 0.0
    tokens_per_second: Optional[float] = None
    retry_count: int = 0
    circuit_breaker_state: str = "CLOSED"
    output_valid: bool = True
    final_status: str = "SUCCESS"
    error_summary: Optional[str] = None

class RouterTelemetry:
    """In-memory telemetry collector with export capability."""

    def __init__(self, max_records: int = 500):
        self.max_records = max_records
        self._records: List[RouterTelemetryRecord] = []

    def record(self, record: RouterTelemetryRecord) -> None:
        """Add record and prune older entries if capacity exceeded."""
        self._records.append(record)
        if len(self._records) > self.max_records:
            self._records.pop(0)

    def get_records(self) -> List[RouterTelemetryRecord]:
        """Return shallow copy of recorded telemetry."""
        return list(self._records)

    def clear(self) -> None:
        """Reset telemetry storage."""
        self._records.clear()
