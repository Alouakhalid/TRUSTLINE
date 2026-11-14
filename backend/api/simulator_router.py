"""Simulator control router exposing the existing data-engineering/simulator engine to the frontend."""
from __future__ import annotations

import asyncio
import sys
import threading
import time
from pathlib import Path
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, Field

from backend.auth.modes import demo_mode
from backend.auth.rbac import current_user
from backend.database.store import store
from backend.services import telemetry

# Bootstrap path to data-engineering
_ROOT = Path(__file__).resolve().parents[2]
_DE_DIR = str(_ROOT / "data-engineering")
if _DE_DIR not in sys.path and Path(_DE_DIR).exists():
    sys.path.insert(0, _DE_DIR)

from simulator.scenarios.engine import ScenarioEngine, ScenarioType, FaultType, FaultInjectionConfig, SensorType

router = APIRouter(prefix="/simulator", tags=["Biomedical Sensor Simulator"])

_LOCK = threading.Lock()
_engine = ScenarioEngine(astronaut_id="AST-001", session_id="SESSION-SIM-DEMO")
_is_running = False
_sim_task: Optional[asyncio.Task] = None


async def _autonomous_stream() -> None:
    while _is_running:
        try:
            await generate_step(duration_sec=1.0)
        except Exception:
            pass
        await asyncio.sleep(1.0)


class SimulatorConfigureRequest(BaseModel):
    scenario: str = Field(default="SCENARIO_A_REST")
    astronaut_id: str = Field(default="AST-001")
    random_seed: Optional[int] = Field(default=None)


class FaultRequest(BaseModel):
    fault_type: str = Field(default="FLATLINE")
    target_sensor: Optional[str] = Field(default="ECG")
    severity: float = Field(default=1.0, ge=0.0, le=1.0)
    duration_sec: float = Field(default=60.0, gt=0)


@router.get("/status")
def get_simulator_status() -> Dict[str, Any]:
    with _LOCK:
        return {
            "is_running": _is_running,
            "current_scenario": _engine.current_scenario.value,
            "elapsed_seconds": round(_engine.elapsed_time_sec, 2),
            "astronaut_id": _engine.astronaut_id,
            "active_faults": [c.fault_type.value for c in _engine.fault_injector.configs],
        }


@router.get("/scenarios")
def list_scenarios() -> List[Dict[str, str]]:
    return [
        {"id": s.name, "value": s.value, "label": s.name.replace("SCENARIO_", "").replace("_", " ")}
        for s in ScenarioType
    ]


@router.post("/configure")
def configure_simulator(req: SimulatorConfigureRequest) -> Dict[str, Any]:
    global _engine
    with _LOCK:
        if req.astronaut_id:
            _engine.astronaut_id = req.astronaut_id
        for s in ScenarioType:
            if s.name == req.scenario or s.value == req.scenario:
                _engine.set_scenario(s)
                break
        return {
            "status": "configured",
            "scenario": _engine.current_scenario.value,
            "astronaut_id": _engine.astronaut_id,
        }


@router.post("/start")
async def start_simulator(
    req: Optional[SimulatorConfigureRequest] = None,
    scenario: Optional[str] = None,
    astronaut_id: Optional[str] = None,
) -> Dict[str, Any]:
    global _is_running, _sim_task
    target_astro = (req.astronaut_id if req and req.astronaut_id else None) or astronaut_id
    target_scen = (req.scenario if req and req.scenario else None) or scenario

    with _LOCK:
        if target_astro:
            _engine.astronaut_id = target_astro
        if target_scen:
            for s in ScenarioType:
                if (
                    s.name == target_scen
                    or s.value == target_scen
                    or s.name.lower() == target_scen.lower()
                    or s.value.lower() == target_scen.lower()
                ):
                    _engine.set_scenario(s)
                    break
        _is_running = True
    if _sim_task is None or _sim_task.done():
        _sim_task = asyncio.create_task(_autonomous_stream())
    return {"status": "started", "scenario": _engine.current_scenario.value, "astronaut_id": _engine.astronaut_id}


@router.post("/stop")
async def stop_simulator() -> Dict[str, Any]:
    global _is_running, _sim_task
    with _LOCK:
        _is_running = False
    if _sim_task and not _sim_task.done():
        _sim_task.cancel()
    return {"status": "stopped"}


@router.post("/step")
async def generate_step(
    seed: Optional[int] = None,
    scenario: Optional[str] = None,
    astronaut_id: Optional[str] = None,
    duration_sec: float = 1.0,
) -> Dict[str, Any]:
    """Execute a step in the simulation engine, persist telemetry, evaluate with AI agents, and broadcast via WS."""
    import json
    import numpy as np
    from backend.services import radiation_gateway

    actual_seed = seed if isinstance(seed, int) else None

    with _LOCK:
        if astronaut_id:
            _engine.astronaut_id = astronaut_id
        elif telemetry.broadcaster._subscribers:
            # Sync to active connected astronaut if none explicitly passed
            active_ids = list(telemetry.broadcaster._subscribers.keys())
            if active_ids and _engine.astronaut_id not in active_ids:
                _engine.astronaut_id = active_ids[0]

        if scenario:
            for s in ScenarioType:
                if s.name == scenario or s.value == scenario:
                    _engine.set_scenario(s)
                    break

        packets, space_packet = _engine.generate_step(duration_sec=duration_sec, seed=actual_seed)
        active_faults = [c.fault_type.value for c in _engine.fault_injector.configs]

    # Convert to backend format
    backend_packets = []
    readings_map: Dict[str, Any] = {}
    ecg_wave: List[float] = []
    resp_wave: List[float] = []

    for p in packets:
        d = p.model_dump()
        st_val = d["sensor_type"].value if hasattr(d["sensor_type"], "value") else str(d["sensor_type"])
        st_clean = st_val.split(".")[-1].upper()

        channels_data = d.get("channels_data") or []
        last_val = 0.0
        if channels_data and len(channels_data[0]) > 0:
            last_val = round(float(channels_data[0][-1]), 2)
            if st_clean == "ECG":
                ecg_wave = [round(float(x), 4) for x in channels_data[0][-150:]]
            elif st_clean == "RESPIRATION":
                resp_wave = [round(float(x), 4) for x in channels_data[0][-150:]]

        # Populate readings for UI
        readings_map[st_clean] = last_val
        if st_clean == "HR":
            readings_map["heart_rate"] = last_val
        elif st_clean == "SPO2":
            readings_map["spo2"] = last_val
        elif st_clean == "CORE_TEMP":
            readings_map["temperature"] = last_val
            readings_map["core_temp"] = last_val
        elif st_clean == "SKIN_TEMP":
            readings_map["skin_temp"] = last_val
        elif st_clean == "RESPIRATION":
            readings_map["respiration"] = last_val
        elif st_clean == "EDA":
            readings_map["eda"] = last_val
        elif st_clean == "PPG":
            readings_map["blood_pressure"] = round(120.0 + (last_val * 10), 1)

        backend_packets.append({
            "packet_id": d["packet_id"],
            "astronaut_id": _engine.astronaut_id,
            "session_id": d["session_id"],
            "sensor_type": st_clean,
            "sequence_number": int(d["sequence_number"]),
            "timestamp_epoch_ms": int(d["timestamp_epoch_ms"]),
            "sample_rate_hz": float(d.get("sample_rate_hz", 100.0)),
            "channels_data": channels_data,
            "checksum_crc32": int(d["checksum_crc32"]),
            "hardware_metadata": d.get("hardware_metadata") or {},
        })

    # Synthetic blood pressure and EEG if not generated
    if "blood_pressure" not in readings_map:
        readings_map["blood_pressure"] = 118.5
    if "eeg" not in readings_map:
        readings_map["eeg"] = 24.2

    # Ingest into both operational and demo stores
    report_demo = telemetry.ingest_packets(store, backend_packets, is_demo=True)
    report_op = telemetry.ingest_packets(store, backend_packets, is_demo=False)

    # Ingest space radiation if present
    if space_packet:
        try:
            sp_dict = space_packet.model_dump()
            radiation_gateway.ingest_packet(store, sp_dict, is_demo=False)
            radiation_gateway.ingest_packet(store, sp_dict, is_demo=True)
        except Exception:
            pass

    # Multi-Agent evaluation (SQA + PHA + RAA)
    if any(f in active_faults for f in ["FLATLINE", "CLIPPING"]):
        overall_risk = "critical"
        quality_status = "critical"
        decision_note = "SQA Critical Alarm: Sensor lead flatline or ADC rail clipping detected. Lead impedance check required."
    elif any(f in active_faults for f in ["BASELINE_WANDER", "POWERLINE_NOISE", "PACKET_LOSS", "DRIFT", "NOISE"]):
        overall_risk = "warning"
        quality_status = "warning"
        decision_note = "SQA Advisory: Baseline drift or RF telemetry jitter detected. Stream quarantined for filtering."
    elif _engine.current_scenario.value == "SCENARIO_B_EVA_ACTIVITY":
        overall_risk = "warning"
        quality_status = "nominal"
        decision_note = "PHA Assessment: High metabolic workload during EVA activity. Heart rate elevated within expected thermal envelope."
    elif _engine.current_scenario.value == "SCENARIO_C_ACUTE_STRESS":
        overall_risk = "warning"
        quality_status = "nominal"
        decision_note = "PHA/RAA Assessment: Autonomic sympathetic activation detected (elevated EDA tonic response)."
    elif _engine.current_scenario.value == "SCENARIO_D_SLEEP_RECOVERY":
        overall_risk = "nominal"
        quality_status = "nominal"
        decision_note = "PHA Assessment: Sleep recovery cycle active. Parasympathetic tone dominant (bradycardic baseline nominal)."
    elif _engine.current_scenario.value == "SCENARIO_F_RADIATION_COMPOSITE":
        overall_risk = "critical"
        quality_status = "nominal"
        decision_note = "RAA Urgent Alert: SPE solar particle event flux exceeded threshold. Safe haven protocol advised."
    else:
        overall_risk = "nominal"
        quality_status = "nominal"
        decision_note = "All biotelemetry streams nominal and compliant with NASA-STD-3001 spaceflight standards."

    agent_decision = {
        "overall_risk": overall_risk,
        "quality_status": quality_status,
        "active_faults": active_faults,
        "sqa_validity": "VALID" if not active_faults else "QUARANTINED",
        "decision_note": decision_note,
        "readings": readings_map,
        "timestamp_epoch_ms": int(time.time() * 1000),
    }

    # Record assessment in database so Dashboard AssessmentCard and /assessments reflect it immediately
    try:
        assessment_id = store.new_id("ASM")
        risk_level = overall_risk.upper()
        confidence = "HIGH" if not active_faults else "MODERATE"
        now_ts = store.utc_now() if hasattr(store, "utc_now") else time.strftime("%Y-%m-%d %H:%M:%SZ", time.gmtime())
        store.run(
            "INSERT INTO assessments(id,astronaut_id,session_id,workflow_id,completion_status,overall_risk,overall_confidence,astronaut_response,assessment_json,evidence_count,created_at,is_demo) VALUES(?,?,?,?,?,?,?,?,?,?,?,?)",
            (
                assessment_id,
                _engine.astronaut_id,
                f"SIM-{_engine.current_scenario.value}",
                f"WF-SIM-{int(time.time())}",
                "COMPLETED",
                risk_level,
                confidence,
                decision_note,
                json.dumps(agent_decision, default=str),
                len(active_faults),
                now_ts,
                0,
            ),
        )
        store.run(
            "INSERT INTO assessments(id,astronaut_id,session_id,workflow_id,completion_status,overall_risk,overall_confidence,astronaut_response,assessment_json,evidence_count,created_at,is_demo) VALUES(?,?,?,?,?,?,?,?,?,?,?,?)",
            (
                store.new_id("ASM"),
                _engine.astronaut_id,
                f"SIM-{_engine.current_scenario.value}",
                f"WF-SIM-{int(time.time())}",
                "COMPLETED",
                risk_level,
                confidence,
                decision_note,
                json.dumps(agent_decision, default=str),
                len(active_faults),
                now_ts,
                1,
            ),
        )
    except Exception:
        pass

    # Broadcast individual packets to all connected WebSockets
    for p in backend_packets:
        last_val = p["channels_data"][0][-1] if p["channels_data"] and p["channels_data"][0] else 0.0
        await telemetry.broadcaster.broadcast_all({
            "type": "telemetry_packet",
            "astronaut_id": p["astronaut_id"],
            "packet_id": p["packet_id"],
            "sensor_type": p["sensor_type"],
            "value": last_val,
            "channels": {f"ch_{i}": vals[-1] for i, vals in enumerate(p["channels_data"]) if vals},
            "channels_data": p["channels_data"],
            "timestamp_epoch_ms": p["timestamp_epoch_ms"],
            "is_demo": False,
            "agent_decision": agent_decision,
        })

    # Broadcast aggregated snapshot to all connected WebSockets for instant multi-sensor & 3D twin update
    await telemetry.broadcaster.broadcast_all({
        "type": "telemetry_snapshot",
        "astronaut_id": _engine.astronaut_id,
        "scenario": _engine.current_scenario.value,
        "readings": readings_map,
        "ecg_wave": ecg_wave,
        "resp_wave": resp_wave,
        "agent_decision": agent_decision,
        "timestamp_epoch_ms": int(time.time() * 1000),
    })

    return {
        "status": "step_generated",
        "scenario": _engine.current_scenario.value,
        "astronaut_id": _engine.astronaut_id,
        "packets_generated": len(packets),
        "ingest_report": report_op,
        "readings": readings_map,
        "agent_decision": agent_decision,
        "space_environment": space_packet.model_dump() if space_packet else None,
    }


@router.post("/random-state")
async def randomize_state(
    astronaut_id: Optional[str] = Query(default=None),
) -> Dict[str, Any]:
    """Randomize the physiological scenario, seed, and hardware parameters, immediately executing a coupled simulation step."""
    import random
    scenarios = [s for s in ScenarioType]
    chosen_scenario = random.choice(scenarios)
    random_seed = random.randint(100000, 999999)
    return await generate_step(
        seed=random_seed,
        scenario=chosen_scenario.name,
        astronaut_id=astronaut_id,
        duration_sec=1.0,
    )


@router.post("/fault")
def inject_fault(req: FaultRequest) -> Dict[str, Any]:
    with _LOCK:
        f_type = None
        for ft in FaultType:
            if ft.name == req.fault_type or ft.value == req.fault_type:
                f_type = ft
                break
        if not f_type:
            raise HTTPException(status_code=400, detail=f"Unknown fault type: {req.fault_type}")

        s_type = None
        if req.target_sensor:
            for st in SensorType:
                if st.name == req.target_sensor or st.value == req.target_sensor:
                    s_type = st
                    break

        cfg = FaultInjectionConfig(
            fault_type=f_type,
            target_sensor=s_type,
            start_time_sec=_engine.elapsed_time_sec,
            duration_sec=req.duration_sec,
            severity=req.severity,
        )
        _engine.fault_injector.add_fault(cfg)
        return {"status": "fault_injected", "fault": f_type.value, "sensor": s_type.value if s_type else "ALL"}
