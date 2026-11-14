"""Unit tests for Sensor Registry and Telemetry Schemas."""
import pytest
from simulator.schemas import SensorType, TelemetryPacket, SensorDefinition
from simulator.registry import SensorRegistry, default_sensor_registry


def test_registry_contains_all_core_sensors():
    """Verify all 9 clinical and biomechanical sensors are registered."""
    reg = SensorRegistry()
    sensors = reg.list_sensors()
    assert len(sensors) >= 9

    expected_types = {
        SensorType.ECG,
        SensorType.PPG,
        SensorType.HR,
        SensorType.SPO2,
        SensorType.SKIN_TEMP,
        SensorType.CORE_TEMP,
        SensorType.EDA,
        SensorType.RESPIRATION,
        SensorType.ACCELEROMETER,
        SensorType.GYROSCOPE
    }
    registered_types = {s.sensor_type for s in sensors}
    assert expected_types.issubset(registered_types)


def test_sampling_rates_and_ranges():
    """Verify sampling rates and physiological bounds comply with aerospace specs."""
    reg = default_sensor_registry
    ecg = reg.get_sensor(SensorType.ECG)
    assert ecg is not None
    assert ecg.default_sampling_rate_hz == 256.0
    assert ecg.unit == "mV"
    assert ecg.channels_count == 3
    assert ecg.nominal_range_min == -3.0
    assert ecg.nominal_range_max == 3.0

    eda = reg.get_sensor(SensorType.EDA)
    assert eda is not None
    assert eda.default_sampling_rate_hz == 4.0
    assert eda.unit == "µS"

    acc = reg.get_sensor(SensorType.ACCELEROMETER)
    assert acc is not None
    assert acc.channels_count == 3
    assert acc.default_sampling_rate_hz == 32.0


def test_telemetry_packet_crc32_and_verification():
    """Verify packet CRC32 computation and integrity verification."""
    data = [[0.12, 0.45, 0.98]]
    crc = TelemetryPacket.compute_crc32("ECG", 1, 1700000000000, data)
    assert isinstance(crc, int)

    pkt = TelemetryPacket(
        packet_id="PKT-001",
        sequence_number=1,
        astronaut_id="AST-002",
        session_id="SESS-001",
        timestamp_epoch_ms=1700000000000,
        sensor_type=SensorType.ECG,
        sample_rate_hz=256.0,
        channels_data=data,
        checksum_crc32=crc
    )
    assert pkt.verify_checksum() is True

    # Tamper with data and verify failure
    tampered_pkt = pkt.model_copy(update={"checksum_crc32": crc + 999})
    assert tampered_pkt.verify_checksum() is False


def test_astronaut_identity_cannot_be_empty():
    """Verify validation error when astronaut_id is empty string."""
    with pytest.raises(ValueError):
        TelemetryPacket(
            packet_id="PKT-002",
            sequence_number=1,
            astronaut_id="   ",
            session_id="SESS-001",
            timestamp_epoch_ms=1700000000000,
            sensor_type=SensorType.ECG,
            sample_rate_hz=256.0,
            channels_data=[[0.1]],
            checksum_crc32=12345
        )
