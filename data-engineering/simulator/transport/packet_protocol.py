"""Packet framing, serialization, and cryptographic transmission validation."""
import json
import hashlib
from typing import Dict, Any, Tuple
from ..schemas import TelemetryPacket, SpaceEnvironmentPacket, SensorType


class PacketProtocol:
    """Handles serialization, framing, and data integrity verification for telemetry transmission."""

    @staticmethod
    def encode_telemetry_packet(packet: TelemetryPacket) -> str:
        """Serialize a TelemetryPacket into a JSON transmission frame."""
        return packet.model_dump_json()

    @staticmethod
    def decode_telemetry_packet(payload_str: str) -> Tuple[bool, TelemetryPacket, str]:
        """Deserialize and verify transmission integrity of a TelemetryPacket frame.

        Returns:
            is_valid: bool (True if deserialized and CRC32 matches)
            packet: TelemetryPacket
            error_message: str
        """
        try:
            data = json.loads(payload_str)
            pkt = TelemetryPacket(**data)
            if not pkt.verify_checksum():
                return False, pkt, f"CRC32 mismatch: expected {pkt.checksum_crc32}"
            return True, pkt, ""
        except Exception as e:
            raise ValueError(f"Failed to decode telemetry packet frame: {str(e)}")

    @staticmethod
    def compute_sha256(payload_str: str) -> str:
        """Compute SHA-256 digest of payload for cryptographic auditing."""
        return hashlib.sha256(payload_str.encode("utf-8")).hexdigest()
