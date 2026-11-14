"""Unit tests for Transport protocols, REST API, and SQA Ingestion Bridge."""
import pytest
from pathlib import Path
from starlette.testclient import TestClient
from simulator.schemas import TelemetryPacket, SensorType, ScenarioType
from simulator.transport.packet_protocol import PacketProtocol
from simulator.transport.rest_api import app, global_engine
from simulator.ingestion_bridge import IngestionBridge


@pytest.fixture
def api_client():
    return TestClient(app)


def test_packet_protocol_encode_decode():
    """Verify serialization and deserialization of telemetry frames."""
    data = [[0.1, 0.2], [0.3, 0.4], [0.5, 0.6]]
    crc = TelemetryPacket.compute_crc32("ECG", 10, 1700000000000, data)
    pkt = TelemetryPacket(
        packet_id="PKT-ENC-001",
        sequence_number=10,
        astronaut_id="AST-002",
        session_id="SESS-002",
        timestamp_epoch_ms=1700000000000,
        sensor_type=SensorType.ECG,
        sample_rate_hz=256.0,
        channels_data=data,
        checksum_crc32=crc
    )

    encoded_str = PacketProtocol.encode_telemetry_packet(pkt)
    assert isinstance(encoded_str, str)
    is_valid, decoded_pkt, err = PacketProtocol.decode_telemetry_packet(encoded_str)

    assert is_valid is True
    assert decoded_pkt.packet_id == "PKT-ENC-001"
    assert decoded_pkt.sequence_number == 10
    assert err == ""


def test_rest_api_endpoints(api_client):
    """Verify REST health, status, scenario listing, and control endpoints."""
    # Health probe
    r_health = api_client.get("/health")
    assert r_health.status_code == 200
    assert r_health.json()["status"] == "ok"

    # Status probe
    r_status = api_client.get("/api/simulator/status")
    assert r_status.status_code == 200
    assert "current_scenario" in r_status.json()

    # Scenarios listing
    r_scen = api_client.get("/api/simulator/scenarios")
    assert r_scen.status_code == 200
    assert len(r_scen.json()) >= 6

    # Start simulation
    r_start = api_client.post("/api/simulator/start", json={
        "scenario": ScenarioType.SCENARIO_C_ACUTE_STRESS.value,
        "astronaut_id": "AST-003",
        "session_id": "SESS-REST-01"
    })
    assert r_start.status_code == 200
    assert r_start.json()["scenario"] == "SCENARIO_C_ACUTE_STRESS"

    # Stop simulation
    r_stop = api_client.post("/api/simulator/stop")
    assert r_stop.status_code == 200
    assert r_stop.json()["status"] == "stopped"


def test_rest_api_packet_ingest_and_validation(api_client):
    """Verify /api/telemetry/packet endpoint validates CRC and astronaut identity."""
    data = [[1.2, 1.4]]
    crc = TelemetryPacket.compute_crc32("EDA", 5, 1700000000000, data)
    valid_pkt = TelemetryPacket(
        packet_id="PKT-ING-01",
        sequence_number=5,
        astronaut_id="AST-004",
        session_id="SESS-003",
        timestamp_epoch_ms=1700000000000,
        sensor_type=SensorType.EDA,
        sample_rate_hz=4.0,
        channels_data=data,
        checksum_crc32=crc
    )

    r_ing = api_client.post("/api/telemetry/packet", json=valid_pkt.model_dump())
    assert r_ing.status_code == 200
    assert r_ing.json()["status"] == "accepted"

    # Corrupted CRC should be rejected with 400
    corrupted_dict = valid_pkt.model_dump()
    corrupted_dict["checksum_crc32"] = crc + 42
    r_bad_crc = api_client.post("/api/telemetry/packet", json=corrupted_dict)
    assert r_bad_crc.status_code == 400


def test_ingestion_bridge_assembles_manifest_and_enforces_identity(tmp_path):
    """Verify IngestionBridge creates valid .npy files and SQA manifest with strict identity rules."""
    bridge = IngestionBridge(cache_base_dir=str(tmp_path / "sim_cache"))

    # Ingest 3 seconds of ECG and EDA
    data_ecg = [[0.1 * i for i in range(256)] for _ in range(3)]
    crc_ecg = TelemetryPacket.compute_crc32("ECG", 0, 1700000000000, data_ecg)
    pkt_ecg = TelemetryPacket(
        packet_id="PKT-ECG-1",
        sequence_number=0,
        astronaut_id="AST-005",
        session_id="SESS-TEST-ING",
        timestamp_epoch_ms=1700000000000,
        sensor_type=SensorType.ECG,
        sample_rate_hz=256.0,
        channels_data=data_ecg,
        checksum_crc32=crc_ecg
    )
    bridge.ingest_packet(pkt_ecg)

    # 1. Nominal case with valid astronaut_id
    manifest_file, manifest = bridge.assemble_sqa_manifest(session_id="SESS-TEST-ING", astronaut_id="AST-005")
    assert manifest_file.exists()
    assert manifest.metadata.astronaut_id == "AST-005"
    assert "ECG" in manifest.signals
    assert (manifest_file.parent / "ecg.npy").exists()

    # 2. CRITICAL IDENTITY RULE: When astronaut_id is missing, NEVER assume AST-001
    bridge.buffer["SESS-ANONYMOUS"] = {
        SensorType.ECG: [
            pkt_ecg.model_copy(update={"astronaut_id": "  "})
        ]
    }
    m_anon_file, m_anon = bridge.assemble_sqa_manifest(session_id="SESS-ANONYMOUS", astronaut_id="")
    # Must be AST-UNKNOWN, NOT AST-001
    assert m_anon.metadata.astronaut_id == "AST-UNKNOWN"
    assert m_anon.metadata.astronaut_id != "AST-001"
