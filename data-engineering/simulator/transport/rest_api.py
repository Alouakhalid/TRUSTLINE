"""FastAPI REST endpoints for sensor simulator control and telemetry HTTP fallback."""
from typing import Dict, Any, List, Optional
from fastapi import FastAPI, HTTPException, status
from pydantic import BaseModel, Field

from ..schemas import (
    ScenarioType,
    FaultType,
    FaultInjectionConfig,
    SimulatorStatus,
    TelemetryPacket,
    SpaceEnvironmentPacket,
    SensorType
)
from ..scenarios.engine import ScenarioEngine
from .packet_protocol import PacketProtocol

app = FastAPI(
    title="TRUSTLINE Sensor Simulation & External Telemetry Gateway",
    description="REST & WebSocket API simulating external astronaut monitoring hardware.",
    version="1.0.0"
)

# Global in-process simulation engine
global_engine = ScenarioEngine()
simulation_running = False
packet_history: List[TelemetryPacket] = []


class StartSimulationRequest(BaseModel):
    scenario: ScenarioType = ScenarioType.SCENARIO_A_REST
    astronaut_id: Optional[str] = "AST-001"
    session_id: Optional[str] = "SESSION-SIM-001"


class InjectFaultRequest(BaseModel):
    fault_type: FaultType
    target_sensor: Optional[SensorType] = None
    duration_sec: float = 30.0
    severity: float = 1.0


@app.get("/health", status_code=status.HTTP_200_OK)
def get_health() -> Dict[str, str]:
    """Health check probe."""
    return {"status": "ok", "service": "trustline-simulator-gateway"}


@app.get("/api/simulator/status", response_model=SimulatorStatus)
def get_status() -> SimulatorStatus:
    """Retrieve active status and metrics of the simulator."""
    global simulation_running, global_engine
    return SimulatorStatus(
        is_running=simulation_running,
        current_scenario=global_engine.current_scenario,
        elapsed_seconds=round(global_engine.elapsed_time_sec, 2),
        total_packets_sent=len(packet_history),
        total_bytes_sent=sum(len(p.model_dump_json()) for p in packet_history[-100:]),
        active_sensors=list(global_engine.registry._sensors.keys()),
        active_faults=[c.fault_type for c in global_engine.fault_injector.configs],
        space_environment_active=True
    )


@app.get("/api/simulator/scenarios")
def list_scenarios() -> List[Dict[str, str]]:
    """List available mission operational scenarios."""
    return [
        {"scenario": s.value, "name": s.name} for s in ScenarioType
    ]


@app.post("/api/simulator/start")
def start_simulation(req: StartSimulationRequest) -> Dict[str, Any]:
    """Configure and start mission simulation."""
    global simulation_running, global_engine
    global_engine.astronaut_id = req.astronaut_id if req.astronaut_id else "AST-UNKNOWN"
    global_engine.session_id = req.session_id if req.session_id else "SESSION-UNKNOWN"
    global_engine.set_scenario(req.scenario)
    simulation_running = True
    return {
        "status": "started",
        "scenario": req.scenario.value,
        "astronaut_id": global_engine.astronaut_id,
        "session_id": global_engine.session_id
    }


@app.post("/api/simulator/stop")
def stop_simulation() -> Dict[str, Any]:
    """Stop active simulation."""
    global simulation_running
    simulation_running = False
    return {"status": "stopped"}


@app.post("/api/simulator/fault")
def inject_fault(req: InjectFaultRequest) -> Dict[str, Any]:
    """Dynamically inject a hardware or transmission fault."""
    global global_engine
    cfg = FaultInjectionConfig(
        fault_type=req.fault_type,
        target_sensor=req.target_sensor,
        start_time_sec=global_engine.elapsed_time_sec,
        duration_sec=req.duration_sec,
        severity=req.severity
    )
    global_engine.fault_injector.add_fault(cfg)
    return {"status": "fault_injected", "fault": req.fault_type.value}


@app.post("/api/telemetry/packet")
def ingest_packet_http(packet: TelemetryPacket) -> Dict[str, Any]:
    """Ingest individual telemetry packet via HTTP fallback when WebSockets are unavailable."""
    global packet_history
    if not packet.verify_checksum():
        raise HTTPException(status_code=400, detail="Transmission CRC32 checksum mismatch.")

    # Guard against default identity assumption
    if not packet.astronaut_id or packet.astronaut_id.strip() == "":
        raise HTTPException(status_code=422, detail="Missing astronaut_id. Anonymous telemetry prohibited.")

    packet_history.append(packet)
    if len(packet_history) > 1000:
        packet_history.pop(0)

    return {
        "status": "accepted",
        "packet_id": packet.packet_id,
        "sensor": packet.sensor_type.value,
        "seq": packet.sequence_number
    }
