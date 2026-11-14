"""Ingestion bridge translating external streaming telemetry into TRUSTLINE SQA manifests and Supervisor workflow."""
import json
import os
from pathlib import Path
from typing import Dict, List, Optional, Any, Tuple
import numpy as np

from .schemas import TelemetryPacket, SensorType, SpaceEnvironmentPacket
from .space_environment.space_assessment_bridge import SpaceAssessmentBridge

try:
    from sensor_quality_agent.schemas.input_schema import (
        AstronautHealthManifest,
        RecordingMetadata,
        SensorSignalConfig
    )
except ImportError:
    from agents.sensor_quality.schemas.input_schema import (
        AstronautHealthManifest,
        RecordingMetadata,
        SensorSignalConfig
    )

try:
    from supervisor.workflow.graph import SupervisorWorkflowRunner
    from supervisor.schemas.requests import SupervisorRequest, AstronautInput, InputModality
except ImportError:
    SupervisorWorkflowRunner = None
    SupervisorRequest = None


class IngestionBridge:
    """Translates incoming packets into SQA AstronautHealthManifest and invokes Supervisor orchestrator.

    STRICT ARCHITECTURAL RULES:
    1. LangGraph Supervisor remains the single authoritative orchestrator.
    2. Identity Integrity: Missing astronaut_id NEVER defaults to AST-001. Flagged as AST-UNKNOWN.
    3. Radiation is NOT ML: Radiation data is routed separately to the Evidence Registry, never into ML/SQA.
    """

    def __init__(self, cache_base_dir: str = "data/cache/simulated_signals"):
        self.cache_base_dir = Path(cache_base_dir).resolve()
        self.cache_base_dir.mkdir(parents=True, exist_ok=True)
        self.buffer: Dict[str, Dict[SensorType, List[TelemetryPacket]]] = {}

    def ingest_packet(self, packet: TelemetryPacket) -> None:
        """Accumulate packet into session buffer."""
        # Validate checksum first
        if not packet.verify_checksum():
            raise ValueError(f"Packet {packet.packet_id} failed CRC32 integrity check.")

        session_id = packet.session_id
        if session_id not in self.buffer:
            self.buffer[session_id] = {}
        if packet.sensor_type not in self.buffer[session_id]:
            self.buffer[session_id][packet.sensor_type] = []

        self.buffer[session_id][packet.sensor_type].append(packet)

    def assemble_sqa_manifest(
        self,
        session_id: str,
        astronaut_id: Optional[str] = None
    ) -> Tuple[Path, AstronautHealthManifest]:
        """Convert buffered session packets into .npy signal files and an SQA AstronautHealthManifest.

        Returns:
            manifest_path: Path to astronaut_health_data.json
            manifest: AstronautHealthManifest object
        """
        if session_id not in self.buffer:
            raise KeyError(f"No buffered packets for session '{session_id}'.")

        session_packets = self.buffer[session_id]
        session_dir = self.cache_base_dir / session_id
        session_dir.mkdir(parents=True, exist_ok=True)

        # STRICT IDENTITY RULE: Never assume AST-001 when missing
        effective_astro_id = (astronaut_id or "").strip()
        if not effective_astro_id:
            # Check packet headers
            for st, pkts in session_packets.items():
                if pkts and pkts[0].astronaut_id.strip():
                    effective_astro_id = pkts[0].astronaut_id.strip()
                    break

        if not effective_astro_id or effective_astro_id.upper() == "UNKNOWN":
            effective_astro_id = "AST-UNKNOWN"

        signals_map: Dict[str, SensorSignalConfig] = {}

        # SQA allowed sensors: {"ECG", "EDA", "RESP", "EMG", "ACC", "TEMP"}
        sensor_type_mapping = {
            SensorType.ECG: ("ECG", "ecg.npy", "mV", 256.0),
            SensorType.EDA: ("EDA", "eda.npy", "µS", 4.0),
            SensorType.RESPIRATION: ("RESP", "resp.npy", "a.u.", 32.0),
            SensorType.SKIN_TEMP: ("TEMP", "temp.npy", "°C", 4.0),
            SensorType.ACCELEROMETER: ("ACC", "acc.npy", "g", 32.0)
        }

        for sim_type, (sqa_name, fname, unit, def_fs) in sensor_type_mapping.items():
            if sim_type in session_packets and session_packets[sim_type]:
                pkts = session_packets[sim_type]
                # Sort by sequence number
                pkts_sorted = sorted(pkts, key=lambda p: p.sequence_number)
                # Concatenate channels across packets
                num_ch = len(pkts_sorted[0].channels_data)
                ch_concats = [[] for _ in range(num_ch)]
                fs = pkts_sorted[0].sample_rate_hz

                for p in pkts_sorted:
                    for ch_idx in range(num_ch):
                        ch_concats[ch_idx].extend(p.channels_data[ch_idx])

                if num_ch == 1:
                    arr = np.array(ch_concats[0], dtype=np.float32)
                else:
                    arr = np.array(ch_concats, dtype=np.float32).T

                npy_path = session_dir / fname
                np.save(str(npy_path), arr)

                signals_map[sqa_name] = SensorSignalConfig(
                    file=fname,
                    sampling_rate=fs,
                    unit=unit,
                    channels=num_ch
                )

        metadata = RecordingMetadata(
            astronaut_id=effective_astro_id,
            session_id=session_id,
            recording_id=f"REC-{session_id}",
            data_source="trustline_hardware_simulator",
            device_id="SIM-WEARABLE-V1",
            environment="analog_mission_simulator"
        )

        manifest = AstronautHealthManifest(
            metadata=metadata,
            signals=signals_map
        )

        manifest_file = session_dir / "astronaut_health_data.json"
        with open(manifest_file, "w") as f:
            json.dump(manifest.model_dump(), f, indent=2)

        return manifest_file, manifest

    def execute_supervisor_workflow(
        self,
        session_id: str,
        astronaut_id: Optional[str] = None,
        query_text: str = ""
    ) -> Dict[str, Any]:
        """Trigger the 10-node Supervisor workflow for an ingested session."""
        manifest_file, manifest = self.assemble_sqa_manifest(session_id, astronaut_id)

        if SupervisorWorkflowRunner is None:
            return {
                "manifest_path": str(manifest_file),
                "astronaut_id": manifest.metadata.astronaut_id,
                "status": "MANIFEST_GENERATED_SUPERVISOR_NOT_LOADED"
            }

        runner = SupervisorWorkflowRunner()
        req = SupervisorRequest(
            request_id=f"REQ-SIM-{session_id}",
            astronaut_id=manifest.metadata.astronaut_id,
            session_id=session_id,
            modality=InputModality.MULTIMODAL,
            input_data=AstronautInput(
                text_query=query_text or None,
                sensor_manifest_path=str(manifest_file)
            )
        )
        final_assessment = runner.run(req)
        return {
            "manifest_path": str(manifest_file),
            "astronaut_id": manifest.metadata.astronaut_id,
            "final_assessment": final_assessment
        }
