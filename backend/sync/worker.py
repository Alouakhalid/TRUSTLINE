"""Sync worker: moves queued events through the injectable transport seam.

Correctness model:
- The queue is the source of truth. An event leaves the ``PENDING`` set only
  via an observed successful delivery (``mark_success``) or the retry policy
  (``mark_failure`` → backoff / ``DEAD_LETTER``).
- Checkpoints are observability, not correctness: they record what was
  processed and which transport was last used, so operators can see progress
  after a restart. Recovery never depends on them — unclaimed PENDING events
  are re-claimed regardless.
- Transport swaps are recorded as ``SYNC_TRANSPORT`` provider transitions.
"""
from __future__ import annotations

from typing import Any

from backend.services import transitions
from backend.sync.queue import SyncQueue
from backend.sync.transport import Transport


class SyncWorker:
    def __init__(self, queue: SyncQueue, transport: Transport, is_demo: bool = False, partition: str = "primary") -> None:
        self.queue = queue
        self.db = queue.db
        self.transport = transport
        self.is_demo = is_demo
        self.partition = partition

    def run_once(self, limit: int = 25) -> dict[str, Any]:
        """Process one batch of due events. Never raises for delivery failures."""
        if not self.transport.is_ready():
            return {
                "claimed": 0, "delivered": 0, "failed": 0, "dead_lettered": 0,
                "skipped": f"TRANSPORT_NOT_READY ({self.transport.name})",
                "provider": self.transport.name, "is_demo": self.is_demo,
            }
        events = self.queue.claim_ready(limit=limit, is_demo=self.is_demo)
        report = {"claimed": len(events), "delivered": 0, "failed": 0, "dead_lettered": 0,
                  "skipped": None, "provider": self.transport.name, "is_demo": self.is_demo, "results": []}
        last_event_id: str | None = None
        last_success_at: str | None = None
        for event in events:
            last_event_id = event["id"]
            outcome = self.transport.deliver(event)
            if outcome.get("delivered"):
                self.queue.mark_success(event["id"], is_demo=self.is_demo)
                last_success_at = _utc_now()
                report["delivered"] += 1
                report["results"].append({"id": event["id"], "state": "SYNCED", "provider": outcome.get("provider")})
            else:
                failure = self.queue.mark_failure(event["id"], str(outcome.get("reason") or "unknown"), is_demo=self.is_demo)
                report["failed"] += 1
                if failure["status"] == "DEAD_LETTER":
                    report["dead_lettered"] += 1
                report["results"].append({"id": event["id"], "state": failure["status"], "reason": failure["reason"], "attempts": failure["attempts"]})
        self._record_checkpoint(report, last_event_id, last_success_at)
        self._record_transport_transition(report)
        return report

    def _record_checkpoint(self, report: dict[str, Any], last_event_id: str | None, last_success_at: str | None) -> None:
        existing = self.db.one(
            "SELECT * FROM sync_checkpoints WHERE partition=? AND is_demo=?",
            (self.partition, int(self.is_demo)),
        )
        provider = self.transport.name
        now = _utc_now()
        if existing is None:
            self.db.run(
                "INSERT INTO sync_checkpoints(id,partition,last_event_id,last_success_at,events_processed,delivered_total,failed_total,provider,updated_at,is_demo) VALUES(?,?,?,?,?,?,?,?,?,?)",
                (self.db.new_id("CP"), self.partition, None, None, 0, 0, 0, provider, now, int(self.is_demo)),
            )
            existing = self.db.one("SELECT * FROM sync_checkpoints WHERE partition=? AND is_demo=?", (self.partition, int(self.is_demo)))
        delivered_total = int(existing["delivered_total"]) + report["delivered"]
        failed_total = int(existing["failed_total"]) + report["failed"]
        merged_last_event = last_event_id or existing["last_event_id"]
        merged_last_success = last_success_at or existing["last_success_at"]
        self.db.run(
            "UPDATE sync_checkpoints SET last_event_id=?, last_success_at=?, events_processed=?, delivered_total=?, failed_total=?, provider=?, updated_at=? WHERE partition=? AND is_demo=?",
            (merged_last_event, merged_last_success, int(existing["events_processed"]) + report["claimed"], delivered_total, failed_total, provider, _utc_now(), self.partition, int(self.is_demo)),
        )

    def _record_transport_transition(self, report: dict[str, Any]) -> None:
        if report["delivered"] > 0:
            transitions.record(
                self.db, "SYNC_TRANSPORT", self.transport.name, is_demo=self.is_demo,
                from_state="LOCAL_BUFFER", reason=f"delivered {report['delivered']} event(s)",
            )

    def checkpoint(self) -> dict[str, Any]:
        row = self.db.one(
            "SELECT * FROM sync_checkpoints WHERE partition=? AND is_demo=?",
            (self.partition, int(self.is_demo)),
        )
        if row is None:
            return {
                "id": None,
                "partition": self.partition,
                "last_event_id": None,
                "last_success_at": None,
                "events_processed": 0,
                "delivered_total": 0,
                "failed_total": 0,
                "provider": self.transport.name,
                "updated_at": None,
                "is_demo": bool(self.is_demo),
            }
        item = dict(row)
        item["is_demo"] = bool(item["is_demo"])
        return item


def _utc_now() -> str:
    from backend.database.store import utc_now
    return utc_now()
