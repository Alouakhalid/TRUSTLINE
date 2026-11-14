"""Real-time telemetry ingestion: integrity, isolation, sequence, and WebSocket fan-out.

Packets mirror the simulator's ``TelemetryPacket`` framing so the existing
simulator can stream straight into the mission API. Ingestion enforces:
- CRC32 integrity verification (same algorithm as the simulator),
- duplicate packet detection (unique packet_id per astronaut and mode),
- per-session, per-sensor sequence validation (GAP / DUPLICATE / OUT_OF_ORDER flags),
- astronaut isolation (astronauts may only ingest and read their own feed),
- timestamp preservation (epoch milliseconds stored verbatim),
- Demo isolation (is_demo column; demo packets never mix with operational).

Radiation is NOT handled here: it is environmental instrumentation with its own
service (radiation_gateway) and its own table, never a physiological packet.
"""
from __future__ import annotations

import asyncio
import json
import zlib
from typing import Any

from backend.database.store import SQLiteStore, store, utc_now

ALLOWED_SENSOR_TYPES = {
    "ECG", "PPG", "HR", "SPO2", "SKIN_TEMP", "CORE_TEMP",
    "EDA", "RESPIRATION", "ACCELEROMETER", "GYROSCOPE",
    "EEG", "EMG", "BLOOD_PRESSURE",
}


def compute_crc32(sensor_type: str, sequence_number: int, timestamp_epoch_ms: int, channels: list[list[float]]) -> int:
    """Checksum identical to the simulator's TelemetryPacket.compute_crc32."""
    serialized = f"{sensor_type}:{sequence_number}:{timestamp_epoch_ms}:{channels}".encode("utf-8")
    return zlib.crc32(serialized) & 0xFFFFFFFF


def ingest_packets(db: SQLiteStore, packets: list[dict[str, Any]], is_demo: bool) -> dict[str, Any]:
    """Validate, deduplicate, sequence-check, and persist telemetry packets."""
    report: dict[str, Any] = {"accepted": 0, "duplicates": 0, "checksum_failures": 0,
                              "gaps": 0, "out_of_order": 0, "rejected": [], "results": []}
    for index, packet in enumerate(packets):
        try:
            astronaut_id = str(packet["astronaut_id"]).strip()
            session_id = str(packet["session_id"]).strip()
            sensor_type = str(packet["sensor_type"]).upper().strip()
            sequence_number = int(packet["sequence_number"])
            timestamp_epoch_ms = int(packet["timestamp_epoch_ms"])
            sample_rate_hz = float(packet["sample_rate_hz"])
            channels = packet["channels_data"]
            checksum = int(packet["checksum_crc32"])
            packet_id = str(packet["packet_id"]).strip()
        except (KeyError, TypeError, ValueError) as exc:
            report["rejected"].append({"index": index, "reason": f"invalid packet fields: {exc}"})
            continue
        if not astronaut_id or not session_id or not packet_id:
            report["rejected"].append({"index": index, "reason": "empty identity fields"})
            continue
        if sensor_type not in ALLOWED_SENSOR_TYPES:
            report["rejected"].append({"index": index, "reason": f"unsupported sensor_type {sensor_type}"})
            continue
        if not isinstance(channels, list) or not channels or not all(isinstance(ch, list) for ch in channels):
            report["rejected"].append({"index": index, "reason": "channels_data must be a list of channel arrays"})
            continue
        checksum_ok = compute_crc32(sensor_type, sequence_number, timestamp_epoch_ms, channels) == checksum
        if not checksum_ok:
            report["checksum_failures"] += 1

        existing = db.one(
            "SELECT id FROM telemetry_packets WHERE packet_id=? AND astronaut_id=? AND is_demo=?",
            (packet_id, astronaut_id, int(is_demo)),
        )
        if existing is not None:
            report["duplicates"] += 1
            report["results"].append({"index": index, "packet_id": packet_id, "state": "DUPLICATE", "stored": False})
            continue

        last = db.one(
            "SELECT sequence_number FROM telemetry_packets WHERE astronaut_id=? AND session_id=? AND sensor_type=? AND is_demo=? ORDER BY timestamp_epoch_ms DESC, sequence_number DESC LIMIT 1",
            (astronaut_id, session_id, sensor_type, int(is_demo)),
        )
        if last is None:
            sequence_state = "OK"
        else:
            expected = int(last["sequence_number"]) + 1
            if sequence_number == int(last["sequence_number"]):
                sequence_state = "DUPLICATE"
            elif sequence_number > expected:
                sequence_state = "GAP"
                report["gaps"] += 1
            else:
                sequence_state = "OUT_OF_ORDER"
                report["out_of_order"] += 1

        db.run(
            "INSERT INTO telemetry_packets(id,packet_id,astronaut_id,session_id,sensor_type,sequence_number,sample_rate_hz,channels_json,checksum_crc32,checksum_ok,sequence_state,timestamp_epoch_ms,hardware_metadata_json,received_at,is_demo) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
            (
                db.new_id("TEL"), packet_id, astronaut_id, session_id, sensor_type, sequence_number,
                sample_rate_hz, json.dumps(channels), checksum, int(checksum_ok), sequence_state,
                timestamp_epoch_ms, json.dumps(packet.get("hardware_metadata") or {}), utc_now(), int(is_demo),
            ),
        )
        report["accepted"] += 1
        report["results"].append({
            "index": index, "packet_id": packet_id, "state": sequence_state,
            "stored": True, "checksum_ok": checksum_ok,
        })
    return report


def latest_by_sensor(db: SQLiteStore, astronaut_id: str, is_demo: bool, sensor_type: str | None = None) -> list[dict[str, Any]]:
    sql = (
        "SELECT t.* FROM telemetry_packets t "
        "JOIN (SELECT sensor_type, MAX(timestamp_epoch_ms) AS ts FROM telemetry_packets "
        "      WHERE astronaut_id=? AND is_demo=? GROUP BY sensor_type) m "
        "ON t.sensor_type=m.sensor_type AND t.timestamp_epoch_ms=m.ts "
        "WHERE t.astronaut_id=? AND t.is_demo=?"
    )
    params: list[Any] = [astronaut_id, int(is_demo), astronaut_id, int(is_demo)]
    if sensor_type is not None:
        if sensor_type.upper() not in ALLOWED_SENSOR_TYPES:
            raise ValueError(f"unsupported sensor_type {sensor_type}")
        sql += " AND t.sensor_type=?"
        params.append(sensor_type.upper())
    sql += " ORDER BY t.timestamp_epoch_ms DESC"
    return [_row(row) for row in db.many(sql, tuple(params))]


def history(db: SQLiteStore, astronaut_id: str, is_demo: bool, sensor_type: str | None = None, limit: int = 100) -> list[dict[str, Any]]:
    if limit < 1 or limit > 1000:
        raise ValueError("limit must be between 1 and 1000")
    sql = "SELECT * FROM telemetry_packets WHERE astronaut_id=? AND is_demo=?"
    params: list[Any] = [astronaut_id, int(is_demo)]
    if sensor_type is not None:
        if sensor_type.upper() not in ALLOWED_SENSOR_TYPES:
            raise ValueError(f"unsupported sensor_type {sensor_type}")
        sql += " AND sensor_type=?"
        params.append(sensor_type.upper())
    sql += " ORDER BY timestamp_epoch_ms DESC LIMIT ?"
    params.append(limit)
    return [_row(row) for row in db.many(sql, tuple(params))]


def _row(row: Any) -> dict[str, Any]:
    item = dict(row)
    item["channels_data"] = json.loads(item.pop("channels_json"))
    item["hardware_metadata"] = json.loads(item.pop("hardware_metadata_json"))
    item["checksum_ok"] = bool(item["checksum_ok"])
    item["is_demo"] = bool(item["is_demo"])
    return item


class TelemetryBroadcaster:
    """Fan-out of accepted packets to authorized WebSocket subscribers.

    Backpressure policy: each send is bounded by a short timeout; a slow or dead
    consumer is dropped and counted rather than allowed to stall ingestion.
    """

    def __init__(self) -> None:
        self._subscribers: dict[str, set[Any]] = {}
        self.dropped_connections = 0
        self.broadcast_packets = 0

    def subscribe(self, astronaut_id: str, websocket: Any) -> None:
        self._subscribers.setdefault(astronaut_id, set()).add(websocket)

    def unsubscribe(self, astronaut_id: str, websocket: Any) -> None:
        self._subscribers.get(astronaut_id, set()).discard(websocket)

    def subscriber_count(self, astronaut_id: str) -> int:
        return len(self._subscribers.get(astronaut_id, set()))

    def subscriber_count_total(self) -> int:
        return sum(len(subscribers) for subscribers in self._subscribers.values())

    async def broadcast(self, astronaut_id: str, payload: dict[str, Any], timeout: float = 2.0) -> None:
        connections = list(self._subscribers.get(astronaut_id, set()))
        if not connections:
            return
        message = json.dumps(payload)
        dead = []
        for websocket in connections:
            try:
                await asyncio.wait_for(websocket.send_text(message), timeout=timeout)
                self.broadcast_packets += 1
            except Exception:
                dead.append(websocket)
        for websocket in dead:
            self.unsubscribe(astronaut_id, websocket)
            self.dropped_connections += 1


broadcaster = TelemetryBroadcaster()
