"""Telemetry client utility supporting WebSocket streaming and HTTP fallback."""
import json
import httpx
from typing import Dict, Any, Optional
from ..schemas import TelemetryPacket, SpaceEnvironmentPacket
from .packet_protocol import PacketProtocol


class TelemetryClient:
    """Client for external hardware simulator streaming to TRUSTLINE telemetry gateway."""

    def __init__(self, base_url: str = "http://127.0.0.1:8002", timeout_sec: float = 5.0):
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout_sec

    def send_packet_http(self, packet: TelemetryPacket) -> Dict[str, Any]:
        """Send a single telemetry packet via HTTP REST fallback."""
        url = f"{self.base_url}/api/telemetry/packet"
        with httpx.Client(timeout=self.timeout) as client:
            resp = client.post(url, json=packet.model_dump())
            if resp.status_code != 200:
                raise RuntimeError(f"HTTP ingestion failed ({resp.status_code}): {resp.text}")
            return resp.json()

    def get_simulator_status(self) -> Dict[str, Any]:
        """Fetch status of remote simulation server."""
        url = f"{self.base_url}/api/simulator/status"
        with httpx.Client(timeout=self.timeout) as client:
            resp = client.get(url)
            if resp.status_code != 200:
                raise RuntimeError(f"Failed to fetch status ({resp.status_code}): {resp.text}")
            return resp.json()
