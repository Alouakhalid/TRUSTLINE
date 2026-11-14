"""WebSocket streaming server for real-time external astronaut telemetry broadcasting."""
import asyncio
import json
from typing import Set, Dict, Any, Optional
from fastapi import WebSocket, WebSocketDisconnect
from .rest_api import app, global_engine, simulation_running
from ..schemas import TelemetryPacket, SpaceEnvironmentPacket


class WebSocketConnectionManager:
    """Manages active streaming subscribers to external telemetry feeds."""

    def __init__(self):
        self.active_connections: Set[WebSocket] = set()

    async def connect(self, websocket: WebSocket) -> None:
        """Register and accept new telemetry subscriber."""
        await websocket.accept()
        self.active_connections.add(websocket)

    def disconnect(self, websocket: WebSocket) -> None:
        """Unregister closed subscriber connection."""
        self.active_connections.discard(websocket)

    async def broadcast_packet(self, packet_json: str) -> None:
        """Broadcast telemetry frame to all active subscribers."""
        dead_connections = set()
        for conn in list(self.active_connections):
            try:
                await conn.send_text(packet_json)
            except Exception:
                dead_connections.add(conn)
        for dead in dead_connections:
            self.active_connections.discard(dead)


ws_manager = WebSocketConnectionManager()


@app.websocket("/ws/telemetry")
async def websocket_telemetry_endpoint(websocket: WebSocket) -> None:
    """Real-time streaming endpoint for telemetry packets and space radiation updates."""
    await ws_manager.connect(websocket)
    try:
        while True:
            # Listen for inbound commands (e.g. ping or scenario change)
            data = await websocket.receive_text()
            if data == "ping":
                await websocket.send_text(json.dumps({"type": "pong"}))
    except WebSocketDisconnect:
        ws_manager.disconnect(websocket)
    except Exception:
        ws_manager.disconnect(websocket)
