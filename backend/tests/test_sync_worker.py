"""P07 sync worker + transport seam + failure simulation (fully isolated).

No real network is touched: delivery outcomes come from injected transports.
Covers transient-failure recovery, persistent-failure dead-lettering, offline
queueing, conflict policy, demo isolation, checkpoints, and provider
transition recording.
"""
import pytest

from backend.database.store import store, utc_now
from backend.services import transitions
from backend.sync.queue import SyncQueue, SyncConflict
from backend.sync.transport import GroundTransport, LocalBufferTransport, ProgrammableTransport
from backend.sync.worker import SyncWorker


@pytest.fixture()
def queue(tmp_path):
    store.configure(str(tmp_path / "sync_worker.db"))
    return SyncQueue(store, max_attempts=3)


def test_worker_delivers_records_checkpoint_and_transitions(queue):
    transport = ProgrammableTransport()
    worker = SyncWorker(queue, transport)
    for index in range(3):
        queue.enqueue(f"EVT-{index}", "MEMORY_DELTA", {"index": index})

    report = worker.run_once()
    assert report["claimed"] == 3 and report["delivered"] == 3 and report["failed"] == 0
    assert transport.calls == [
        {"id": "EVT-0", "event_type": "MEMORY_DELTA"},
        {"id": "EVT-1", "event_type": "MEMORY_DELTA"},
        {"id": "EVT-2", "event_type": "MEMORY_DELTA"},
    ]
    assert queue.status() == {"SYNCED": 3}
    checkpoint = worker.checkpoint()
    assert checkpoint["events_processed"] == 3 and checkpoint["delivered_total"] == 3
    assert checkpoint["last_event_id"] == "EVT-2" and checkpoint["last_success_at"] is not None
    assert checkpoint["provider"] == "TEST_TRANSPORT"

    # First successful delivery records LOCAL_BUFFER -> TEST_TRANSPORT; an
    # unchanged state on the next run records nothing (change-detected).
    recorded = transitions.list_transitions(store, kind="SYNC_TRANSPORT")
    assert len(recorded) == 1
    assert recorded[0]["from_state"] == "LOCAL_BUFFER" and recorded[0]["to_state"] == "TEST_TRANSPORT"
    worker.run_once()
    assert len(transitions.list_transitions(store, kind="SYNC_TRANSPORT")) == 1


def test_transient_failures_back_off_then_recover(queue):
    # Two transient failures, then the link recovers.
    transport = ProgrammableTransport(
        outcomes=[
            {"delivered": False, "provider": "TEST_TRANSPORT", "reason": "HTTP 503", "status_code": 503},
            {"delivered": False, "provider": "TEST_TRANSPORT", "reason": "ConnectionError", "status_code": None},
        ]
    )
    worker = SyncWorker(queue, transport)
    queue.enqueue("EVT-RETRY", "MEMORY_DELTA", {"content": "retry me"})

    first = worker.run_once()
    assert first["failed"] == 1 and first["delivered"] == 0
    row = store.one("SELECT * FROM sync_events WHERE id='EVT-RETRY'")
    assert row["status"] == "PENDING" and row["attempts"] == 1
    assert row["next_attempt_at"] > utc_now()  # exponential backoff scheduled

    # Force the backoff window to elapse (test seam: the scheduler, not sleep).
    store.run("UPDATE sync_events SET next_attempt_at=? WHERE id='EVT-RETRY'", ("2020-01-01T00:00:00+00:00",))
    second = worker.run_once()
    assert second["failed"] == 1 and second["delivered"] == 0
    assert store.one("SELECT attempts FROM sync_events WHERE id='EVT-RETRY'")["attempts"] == 2

    # Third attempt: the transient outage is over.
    store.run("UPDATE sync_events SET next_attempt_at=? WHERE id='EVT-RETRY'", ("2020-01-01T00:00:00+00:00",))
    third = worker.run_once()
    assert third["delivered"] == 1 and third["failed"] == 0
    assert queue.status() == {"SYNCED": 1}
    checkpoint = worker.checkpoint()
    assert checkpoint["delivered_total"] == 1 and checkpoint["failed_total"] == 2
    assert checkpoint["last_success_at"] is not None
    # Data never left the spacecraft until the observed success.
    assert [call["id"] for call in transport.calls] == ["EVT-RETRY", "EVT-RETRY", "EVT-RETRY"]
    # Recovery from LOCAL_BUFFER to the transport is recorded exactly once.
    recorded = transitions.list_transitions(store, kind="SYNC_TRANSPORT")
    assert len(recorded) == 1 and recorded[0]["to_state"] == "TEST_TRANSPORT"


def test_persistent_failure_dead_letters_after_max_attempts(queue):
    transport = ProgrammableTransport(default={"delivered": False, "provider": "TEST_TRANSPORT", "reason": "HTTP 500", "status_code": 500})
    worker = SyncWorker(queue, transport)
    queue.enqueue("EVT-STUCK", "TELEMETRY_BATCH", {"packets": 42})

    for expected_attempts in (1, 2, 3):
        store.run("UPDATE sync_events SET next_attempt_at=? WHERE id='EVT-STUCK'", ("2020-01-01T00:00:00+00:00",))
        report = worker.run_once()
        assert report["failed"] == 1
        row = store.one("SELECT * FROM sync_events WHERE id='EVT-STUCK'")
        assert row["attempts"] == expected_attempts
        assert row["status"] == ("DEAD_LETTER" if expected_attempts == 3 else "PENDING")
    assert queue.status() == {"DEAD_LETTER": 1}
    # Dead-lettered events are never re-claimed silently.
    assert queue.claim_ready() == []


def test_offline_local_buffer_keeps_data_local(queue):
    worker = SyncWorker(queue, LocalBufferTransport())
    queue.enqueue("EVT-OFFLINE", "MEMORY_DELTA", {"content": "written during blackout"})
    report = worker.run_once()
    assert report["delivered"] == 0 and report["failed"] == 0 and report["claimed"] == 0
    assert "TRANSPORT_NOT_READY" in report["skipped"] and "LOCAL_BUFFER" in report["skipped"]
    row = store.one("SELECT * FROM sync_events WHERE id='EVT-OFFLINE'")
    assert row["status"] == "PENDING" and row["attempts"] == 0  # still queued, no data loss, attempts preserved
    # The buffer itself never records a successful transport transition.
    assert transitions.list_transitions(store, kind="SYNC_TRANSPORT") == []


def test_unconfigured_ground_transport_is_truthful(queue):
    transport = GroundTransport(endpoint="")
    assert transport.is_ready() is False
    worker = SyncWorker(queue, transport)
    queue.enqueue("EVT-UNCONF", "MEMORY_DELTA", {"content": "x"})
    report = worker.run_once()
    assert report["claimed"] == 0 and report["delivered"] == 0
    assert "TRANSPORT_NOT_READY" in report["skipped"]
    row = store.one("SELECT * FROM sync_events WHERE id='EVT-UNCONF'")
    assert row["status"] == "PENDING" and row["attempts"] == 0  # no attempts burned on misconfiguration


def test_ground_transport_requires_configured_endpoint_and_reports_http():
    assert GroundTransport(endpoint="").deliver({}) == {
        "delivered": False, "provider": "GROUND_HTTP", "reason": "GROUND_ENDPOINT_NOT_CONFIGURED", "status_code": None,
    }
    # Unroutable endpoint -> explicit failure, never a fabricated success.
    unreachable = GroundTransport(endpoint="http://127.0.0.1:9/no-such-ground", timeout=0.5)
    outcome = unreachable.deliver({"id": "X", "event_type": "T", "payload": {}})
    assert outcome["delivered"] is False
    assert outcome["provider"] == "GROUND_HTTP" and outcome["status_code"] is None


def test_conflicts_are_never_silently_overwritten(queue):
    queue.enqueue("EVT-CONFLICT", "MEDICAL_RECORD", {"version": 3})
    with pytest.raises(SyncConflict):
        queue.resolve_conflict("EVT-CONFLICT", local_version=3, ground_version=4)
    row = store.one("SELECT * FROM sync_events WHERE id='EVT-CONFLICT'")
    assert row["status"] == "PENDING"  # untouched until a human resolves it
    result = queue.resolve_conflict("EVT-CONFLICT", local_version=5, ground_version=5)
    assert result["resolution"] == "IDENTICAL_VERSION"
    assert store.one("SELECT status FROM sync_events WHERE id='EVT-CONFLICT'")["status"] == "SYNCED"


def test_demo_queue_is_isolated_from_worker_runs(queue):
    demo_queue = SyncQueue(store, max_attempts=queue.max_attempts)
    queue.enqueue("EVT-OPS", "MEMORY_DELTA", {"scope": "operational"})
    demo_queue.enqueue("EVT-DEMO", "MEMORY_DELTA", {"scope": "demo"}, is_demo=True)
    worker = SyncWorker(queue, ProgrammableTransport())
    report = worker.run_once()
    assert [result["id"] for result in report["results"]] == ["EVT-OPS"]
    demo_status = demo_queue.status(is_demo=True)
    assert demo_status == {"PENDING": 1}
    demo_worker = SyncWorker(demo_queue, ProgrammableTransport(), is_demo=True)
    demo_report = demo_worker.run_once()
    assert [result["id"] for result in demo_report["results"]] == ["EVT-DEMO"]
    # Partitions keep separate checkpoints and transitions.
    assert demo_worker.checkpoint()["is_demo"] is True
    assert transitions.list_transitions(store, kind="SYNC_TRANSPORT", is_demo=True)[0]["is_demo"] is True
    assert all(item["is_demo"] is False for item in transitions.list_transitions(store, kind="SYNC_TRANSPORT", is_demo=False))


def test_transition_kinds_are_validated_and_change_detected(queue):
    with pytest.raises(ValueError):
        transitions.record(store, "NOT_A_KIND", "X")
    first = transitions.record(store, "AI_ROUTING", "LOCAL_ONLY", reason="startup default")
    assert first["from_state"] is None
    assert transitions.record(store, "AI_ROUTING", "LOCAL_ONLY") is None  # unchanged
    flip = transitions.record(store, "AI_ROUTING", "HYBRID", reason="operator override")
    assert flip["from_state"] == "LOCAL_ONLY" and flip["to_state"] == "HYBRID"
    listed = transitions.list_transitions(store, kind="AI_ROUTING")
    assert [item["to_state"] for item in listed] == ["HYBRID", "LOCAL_ONLY"]
    with pytest.raises(ValueError):
        transitions.list_transitions(store, kind="NOT_A_KIND")


def test_admin_sync_run_endpoint_is_truthful(monkeypatch, tmp_path):
    from fastapi.testclient import TestClient
    monkeypatch.setenv("TRUSTLINE_DB_PATH", str(tmp_path / "sync_admin.db"))
    monkeypatch.delenv("TRUSTLINE_GROUND_ENDPOINT", raising=False)
    from backend.api import app as module
    module.store.configure(str(tmp_path / "sync_admin.db"))
    client = TestClient(module.app)
    client.post("/auth/register", json={"username": "chief", "password": "a-very-strong-password", "role": "ADMINISTRATOR"})
    token = client.post("/auth/login", json={"username": "chief", "password": "a-very-strong-password"}).json()["access_token"]
    headers = {"Authorization": f"Bearer {token}"}

    # No ground endpoint configured -> explicit skip, nothing claimed or lost.
    response = client.post("/admin/sync/run", headers=headers, json={"limit": 10})
    assert response.status_code == 200
    body = response.json()
    assert body["claimed"] == 0 and body["delivered"] == 0
    assert "TRANSPORT_NOT_READY" in body["skipped"]
    assert body["provider"] == "GROUND_HTTP"
    assert body["checkpoint"]["is_demo"] is False

    # Demo partition runs its own isolated pass.
    demo = {**headers, "X-Trustline-Mode": "demo"}
    demo_run = client.post("/admin/sync/run", headers=demo, json={"limit": 10}).json()
    assert demo_run["is_demo"] is True and demo_run["checkpoint"]["is_demo"] is True

    # RBAC: officers and astronauts cannot run or inspect sync operations.
    client.post("/auth/register", json={"username": "medic", "password": "a-very-strong-password", "role": "MEDICAL_OFFICER"})
    medic = client.post("/auth/login", json={"username": "medic", "password": "a-very-strong-password"}).json()["access_token"]
    assert client.post("/admin/sync/run", headers={"Authorization": f"Bearer {medic}"}).status_code == 403
    assert client.get("/admin/transitions", headers={"Authorization": f"Bearer {medic}"}).status_code == 403
