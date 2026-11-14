"""Independent connectivity monitors for the TRUSTLINE Mission API.

Every monitor reports its OWN state. A DNS resolution failure must never be
reported as a general network failure and vice versa. Probes are injectable so
tests can simulate failures without touching the real host network.

Monitor classes:

- Connectivity-class (count toward ONLINE/OFFLINE): ``database``, ``dns``,
  ``network``, ``ground_link``, ``cloud_ai``, ``local_ai``.
- Service-health class (reported, never counted as a link): ``sync`` (queue
  health) and ``ws`` (telemetry WebSocket fan-out health).

Default probes perform short, read-only checks:
- ``dns``         resolve the probe host via the OS resolver (no traffic).
- ``network``     one TCP connect to the probe host (443).
- ``local_ai``    HTTP GET on the local Ollama endpoint (/api/tags).
- ``ground_link`` HTTP GET on the ground endpoint root (no credentials).
- ``cloud_ai``    one TCP connect to the cloud AI provider host (443) — a
                  reachability check only; no API call, no credentials sent.
- ``database``    SELECT 1 against the application store.
- ``sync``        queue counters from the local store (DEGRADED on dead-letter).
- ``ws``          telemetry broadcaster liveness + subscriber/drop counters.

An unconfigured endpoint reports ``NOT_CONFIGURED`` — a truthful third state,
distinct from ``UNREACHABLE``.
"""
from __future__ import annotations

import os
import socket
import time
import urllib.error
import urllib.request
from typing import Any, Callable

from backend.database.store import store, utc_now

CONNECTIVITY_MONITORS = ("database", "dns", "network", "ground_link", "cloud_ai", "local_ai")
SERVICE_MONITORS = ("sync", "ws")
MONITOR_NAMES = CONNECTIVITY_MONITORS + SERVICE_MONITORS


def _dns_probe(host: str) -> None:
    socket.getaddrinfo(host, 443)


def _network_probe(host: str, timeout: float = 3.0) -> None:
    with socket.create_connection((host, 443), timeout=timeout):
        pass


def _local_ai_probe(base_url: str, timeout: float = 1.5) -> None:
    with urllib.request.urlopen(f"{base_url.rstrip('/')}/api/tags", timeout=timeout) as response:
        response.read(64)


def _ground_probe(endpoint: str, timeout: float = 2.5) -> None:
    with urllib.request.urlopen(endpoint, timeout=timeout) as response:
        response.read(64)


def _cloud_probe(host: str, timeout: float = 3.0) -> None:
    with socket.create_connection((host, 443), timeout=timeout):
        pass


def _database_probe() -> None:
    if store.one("SELECT 1") is None:
        raise RuntimeError("database probe returned no row")


def _run(probe: Callable[[], None]) -> dict[str, Any]:
    started = time.perf_counter()
    try:
        probe()
    except (OSError, urllib.error.URLError, socket.timeout, RuntimeError, ValueError) as exc:
        return {
            "status": "UNREACHABLE",
            "error_type": type(exc).__name__,
            "latency_ms": round((time.perf_counter() - started) * 1000, 2),
        }
    return {"status": "OK", "latency_ms": round((time.perf_counter() - started) * 1000, 2)}


def _not_configured(monitor: str, detail: str) -> dict[str, Any]:
    return {"status": "NOT_CONFIGURED", "detail": detail, "monitor": monitor}


def _sync_probe(is_demo: bool) -> dict[str, Any]:
    counts = store.many("SELECT status, COUNT(*) AS count FROM sync_events WHERE is_demo=? GROUP BY status", (int(is_demo),))
    counters = {row["status"]: int(row["count"]) for row in counts}
    dead = counters.get("DEAD_LETTER", 0)
    pending = counters.get("PENDING", 0)
    return {
        "status": "DEGRADED" if dead else "OK",
        "pending": pending,
        "dead_letter": dead,
        "is_demo": is_demo,
    }


def _ws_probe() -> dict[str, Any]:
    from backend.services.telemetry import broadcaster
    return {
        "status": "OK",
        "subscribers": broadcaster.subscriber_count_total(),
        "packets_broadcast": broadcaster.broadcast_packets,
        "dropped_connections": broadcaster.dropped_connections,
    }


def probe(
    host: str | None = None,
    dns_probe: Callable[[], None] | None = None,
    network_probe: Callable[[], None] | None = None,
    local_probe: Callable[[], None] | None = None,
    database_probe: Callable[[], None] | None = None,
    ground_probe: Callable[[], None] | None = None,
    cloud_probe: Callable[[], None] | None = None,
    local_url: str | None = None,
    is_demo: bool = False,
) -> dict[str, Any]:
    """Run every monitor independently and return a truthful snapshot."""
    target = host or os.getenv("TRUSTLINE_DNS_PROBE_HOST", "huggingface.co")
    base = local_url or os.getenv("TRUSTLINE_OLLAMA_URL", "http://127.0.0.1:11434")
    endpoint = os.getenv("TRUSTLINE_GROUND_ENDPOINT", "")
    cloud_host = os.getenv("TRUSTLINE_CLOUD_AI_HOST", "api.groq.com")
    dns_probe = dns_probe or (lambda: _dns_probe(target))
    network_probe = network_probe or (lambda: _network_probe(target))
    local_probe = local_probe or (lambda: _local_ai_probe(base))
    database_probe = database_probe or _database_probe
    snapshot: dict[str, Any] = {"checked_at": utc_now(), "is_demo": is_demo}
    for name, monitor in (
        ("database", database_probe),
        ("dns", dns_probe),
        ("network", network_probe),
    ):
        snapshot[name] = _run(monitor)
    if ground_probe is not None:
        snapshot["ground_link"] = _run(ground_probe)
    elif endpoint:
        snapshot["ground_link"] = _run(lambda: _ground_probe(endpoint))
    else:
        snapshot["ground_link"] = _not_configured("ground_link", "TRUSTLINE_GROUND_ENDPOINT not set")
    if cloud_probe is not None:
        snapshot["cloud_ai"] = _run(cloud_probe)
    else:
        snapshot["cloud_ai"] = _run(lambda: _cloud_probe(cloud_host))
    snapshot["local_ai"] = _run(local_probe)
    snapshot["sync"] = _sync_probe(is_demo)
    snapshot["ws"] = _ws_probe()
    reachable = [name for name in CONNECTIVITY_MONITORS if snapshot[name]["status"] == "OK"]
    # Local-first semantics: the local database and service health do not make
    # a mission "online". Offline means no configured EXTERNAL link works.
    external = [name for name in ("dns", "network", "ground_link", "cloud_ai", "local_ai") if snapshot[name]["status"] != "NOT_CONFIGURED"]
    snapshot["summary"] = {
        "reachable": reachable,
        "offline": not any(snapshot[name]["status"] == "OK" for name in external),
        "connectivity_monitors": list(CONNECTIVITY_MONITORS),
        "service_monitors": list(SERVICE_MONITORS),
    }
    return snapshot
