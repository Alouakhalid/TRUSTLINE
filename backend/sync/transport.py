"""Transport seam for ground synchronization.

A transport is the ONLY component allowed to move queued events off the
spacecraft. The worker never talks to the network directly, so tests simulate
offline conditions, partial outages, and provider swaps by injecting transports
— the host network is never touched.

Delivery results are always explicit:
- ``delivered=True``  → the ground system actually accepted the event.
- ``delivered=False`` → nothing was delivered; the queue decides retry policy.
A transport never claims success it did not observe.
"""
from __future__ import annotations

import json
import os
import urllib.error
import urllib.request
from typing import Any, Protocol

DELIVERY_TIMEOUT_SECONDS = 5.0


class Transport(Protocol):
    """Anything that can attempt delivery of one queued event."""

    name: str

    def deliver(self, event: dict[str, Any]) -> dict[str, Any]:
        """Return ``{"delivered": bool, "provider": str, "reason": str|None, "status_code": int|None}``."""
        ...

    def is_ready(self) -> bool:
        """False when the transport cannot even attempt delivery (e.g. unconfigured)."""
        ...


class GroundTransport:
    """HTTP delivery to the configured ground endpoint.

    Read-only reachability is connectivity's job; this transport performs the
    actual ``POST`` of the event payload. Without an endpoint it reports itself
    unready instead of pretending to try.
    """

    name = "GROUND_HTTP"

    def __init__(self, endpoint: str | None = None, timeout: float = DELIVERY_TIMEOUT_SECONDS) -> None:
        self.endpoint = endpoint or os.getenv("TRUSTLINE_GROUND_ENDPOINT", "")
        self.timeout = timeout

    def is_ready(self) -> bool:
        return bool(self.endpoint)

    def deliver(self, event: dict[str, Any]) -> dict[str, Any]:
        if not self.endpoint:
            return {"delivered": False, "provider": self.name, "reason": "GROUND_ENDPOINT_NOT_CONFIGURED", "status_code": None}
        body = json.dumps({
            "event_id": event["id"],
            "event_type": event["event_type"],
            "payload": event["payload"],
        }).encode("utf-8")
        request = urllib.request.Request(
            self.endpoint, data=body, method="POST",
            headers={"Content-Type": "application/json"},
        )
        try:
            with urllib.request.urlopen(request, timeout=self.timeout) as response:
                code = int(response.status)
                response.read(64)
        except urllib.error.HTTPError as exc:
            return {"delivered": False, "provider": self.name, "reason": f"HTTP {exc.code}", "status_code": exc.code}
        except (urllib.error.URLError, OSError, TimeoutError) as exc:
            return {"delivered": False, "provider": self.name, "reason": type(exc).__name__, "status_code": None}
        if 200 <= code < 300:
            return {"delivered": True, "provider": self.name, "reason": None, "status_code": code}
        return {"delivered": False, "provider": self.name, "reason": f"HTTP {code}", "status_code": code}


class LocalBufferTransport:
    """Explicitly-local transport used when nothing off-board is reachable.

    It cannot deliver anything, and it says so: ``is_ready()`` is False so the
    worker skips cleanly and never burns retry attempts toward dead-lettering
    during a routine blackout. Events remain queued, unchanged.
    """

    name = "LOCAL_BUFFER"

    def is_ready(self) -> bool:
        return False

    def deliver(self, event: dict[str, Any]) -> dict[str, Any]:
        return {"delivered": False, "provider": self.name, "reason": "OFFLINE_LOCAL_BUFFER", "status_code": None}


class ProgrammableTransport:
    """Test transport: scripted outcomes per call, records every attempt."""

    def __init__(self, outcomes: list[dict[str, Any]] | None = None, default: dict[str, Any] | None = None) -> None:
        self.name = "TEST_TRANSPORT"
        self.calls: list[dict[str, Any]] = []
        self._script = list(outcomes or [])
        self._default = default or {"delivered": True, "provider": "TEST_TRANSPORT", "reason": None, "status_code": 200}

    def is_ready(self) -> bool:
        return True

    def deliver(self, event: dict[str, Any]) -> dict[str, Any]:
        self.calls.append({"id": event["id"], "event_type": event["event_type"]})
        return self._script.pop(0) if self._script else dict(self._default)


def transport_from_env() -> Transport:
    """Deployment default: the configured ground transport.

    When no ground endpoint is configured the transport reports itself not
    ready; the worker then skips without burning attempts. It never silently
    swaps in a fake success.
    """
    return GroundTransport()
