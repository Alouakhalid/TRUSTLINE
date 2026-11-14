"""Environmental radiation telemetry gateway.

Radiation is spacecraft environmental instrumentation. It is stored in its own
table, exposed through its own routes, and is NEVER merged into physiological
telemetry or ML feature streams (architectural rule inherited from
``data-engineing/simulator/space_environment/radiation_model.py``).

The alert level arrives with each packet from the simulator's RadiationModel;
this gateway additionally exposes the NASA-STD-3001 Vol 1 Rev C dose-limit
table (imported from the existing module, not restated) for UI reference.
"""
from __future__ import annotations

import importlib.util
import json
import threading
from typing import Any

from backend.database.store import SQLiteStore, store, utc_now
from backend.services.integrations import data_engineering_path

_LOCK = threading.Lock()
_limits_cache: dict[str, Any] | None = None


def nasa_limits() -> dict[str, Any]:
    """Load the existing NASA-STD-3001 limits table (never redefined here)."""
    global _limits_cache
    if _limits_cache is not None:
        return _limits_cache
    with _LOCK:
        if _limits_cache is not None:
            return _limits_cache
        module_file = data_engineering_path("simulator/space_environment/nasa_standards.py")
        spec = importlib.util.spec_from_file_location("trustline_nasa_standards", module_file)
        if spec is None or spec.loader is None:
            raise ImportError(f"NASA standards module not found at {module_file}")
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        limits = module.NASA_RADIATION_LIMITS
        _limits_cache = {
            "standard": "NASA-STD-3001 Volume 1 Revision C Table 2",
            "blood_forming_organs_30d_msv": limits.blood_forming_organs_30d_msv,
            "eye_lens_30d_msv": limits.eye_lens_30d_msv,
            "skin_30d_msv": limits.skin_30d_msv,
            "blood_forming_organs_1yr_msv": limits.blood_forming_organs_1yr_msv,
            "eye_lens_1yr_msv": limits.eye_lens_1yr_msv,
            "skin_1yr_msv": limits.skin_1yr_msv,
            "spe_acute_action_threshold_microgy_h": limits.spe_acute_action_threshold_microgy_h,
        }
        return _limits_cache


def ingest_packet(db: SQLiteStore, packet: dict[str, Any], is_demo: bool) -> dict[str, Any]:
    """Store one environmental packet verbatim (duplicates rejected, not silently overwritten)."""
    try:
        packet_id = str(packet["packet_id"]).strip()
        timestamp_epoch_ms = int(packet["timestamp_epoch_ms"])
        dose_rate = float(packet["dose_rate_microgy_h"])
        equivalent = float(packet["equivalent_dose_rate_msv_h"])
        cumulative = float(packet["cumulative_mission_dose_msv"])
    except (KeyError, TypeError, ValueError) as exc:
        raise ValueError(f"invalid radiation packet fields: {exc}") from exc
    if not packet_id or timestamp_epoch_ms <= 0:
        raise ValueError("packet_id required and timestamp_epoch_ms must be positive")
    if dose_rate < 0 or equivalent < 0 or cumulative < 0:
        raise ValueError("radiation dose fields must be non-negative")
    alert_level = str(packet.get("alert_level", "NOMINAL")).upper()
    if alert_level not in {"NOMINAL", "ADVISORY", "WARNING", "ALARM"}:
        raise ValueError(f"unsupported alert_level {alert_level}")
    existing = db.one("SELECT id FROM radiation_packets WHERE packet_id=? AND is_demo=?", (packet_id, int(is_demo)))
    if existing is not None:
        return {"packet_id": packet_id, "stored": False, "duplicate": True}
    record_id = db.new_id("RAD")
    db.run(
        "INSERT INTO radiation_packets(id,packet_id,timestamp_epoch_ms,dose_rate_microgy_h,equivalent_dose_rate_msv_h,cumulative_mission_dose_msv,spe_active,spe_flux_pfu,shielding_thickness_g_cm2,alert_level,received_at,is_demo) VALUES(?,?,?,?,?,?,?,?,?,?,?,?)",
        (
            record_id, packet_id, timestamp_epoch_ms, dose_rate, equivalent, cumulative,
            int(bool(packet.get("spe_active", False))), float(packet.get("spe_flux_pfu", 0.0)),
            float(packet.get("shielding_thickness_g_cm2", 10.0)), alert_level, utc_now(), int(is_demo),
        ),
    )
    return {"id": record_id, "packet_id": packet_id, "stored": True, "duplicate": False}


def latest_packet(db: SQLiteStore, is_demo: bool) -> dict[str, Any] | None:
    row = db.one("SELECT * FROM radiation_packets WHERE is_demo=? ORDER BY timestamp_epoch_ms DESC LIMIT 1", (int(is_demo),))
    if row is None:
        return None
    item = dict(row)
    item["spe_active"] = bool(item["spe_active"])
    item["is_demo"] = bool(item["is_demo"])
    return item


def packet_history(db: SQLiteStore, is_demo: bool, limit: int = 100) -> list[dict[str, Any]]:
    if limit < 1 or limit > 1000:
        raise ValueError("limit must be between 1 and 1000")
    rows = db.many("SELECT * FROM radiation_packets WHERE is_demo=? ORDER BY timestamp_epoch_ms DESC LIMIT ?", (int(is_demo), limit))
    result = []
    for row in rows:
        item = dict(row)
        item["spe_active"] = bool(item["spe_active"])
        item["is_demo"] = bool(item["is_demo"])
        result.append(item)
    return result


def serialize(payload: Any) -> str:
    return json.dumps(payload)
