import pytest

from backend.database.store import SQLiteStore
from backend.sync.queue import SyncConflict, SyncQueue


def test_enqueue_is_idempotent_and_demo_scoped():
    queue = SyncQueue(SQLiteStore(":memory:"))
    first = queue.enqueue("EVT-1", "TELEMETRY", {"sequence": 1})
    duplicate = queue.enqueue("EVT-1", "TELEMETRY", {"sequence": 1})
    demo = queue.enqueue("EVT-DEMO-1", "TELEMETRY", {"sequence": 1}, is_demo=True)
    assert first["deduplicated"] is False
    assert duplicate["deduplicated"] is True
    assert demo["deduplicated"] is False
    assert queue.status() == {"PENDING": 1}
    assert queue.status(is_demo=True) == {"PENDING": 1}


def test_retry_backoff_and_dead_letter():
    queue = SyncQueue(SQLiteStore(":memory:"), max_attempts=2)
    queue.enqueue("EVT-2", "MEDICAL_UPDATE", {"version": 1})
    first = queue.mark_failure("EVT-2", "ground timeout")
    assert first["status"] == "PENDING"
    assert first["attempts"] == 1
    second = queue.mark_failure("EVT-2", "ground timeout")
    assert second["status"] == "DEAD_LETTER"
    assert queue.status() == {"DEAD_LETTER": 1}


def test_conflicts_are_never_silently_overwritten():
    queue = SyncQueue(SQLiteStore(":memory:"))
    queue.enqueue("EVT-3", "MEDICAL_UPDATE", {"version": 2})
    with pytest.raises(SyncConflict):
        queue.resolve_conflict("EVT-3", local_version=2, ground_version=3)
    assert queue.status() == {"PENDING": 1}
    assert queue.resolve_conflict("EVT-3", local_version=2, ground_version=2)["status"] == "SYNCED"
