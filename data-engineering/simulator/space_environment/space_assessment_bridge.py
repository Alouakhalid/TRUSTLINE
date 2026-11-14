"""Bridge integrating environmental radiation metrics into TRUSTLINE Evidence Registry without touching ML."""
import uuid
from datetime import datetime
from typing import List, Dict, Any, Optional

try:
    from agents.risk_assessment.schemas.evidence import (
        NormalizedEvidenceItem,
        RiskDomain,
        EvidenceSourceType,
        EvidenceValidity
    )
except ImportError:
    from supervisor.schemas.evidence import (  # fallback if loaded in isolation
        NormalizedEvidenceItem,
        RiskDomain,
        EvidenceSourceType,
        EvidenceValidity
    )

from ..schemas import SpaceEnvironmentPacket


class SpaceAssessmentBridge:
    """Translates physical space radiation telemetry into clinical/operational NormalizedEvidenceItem records.

    CRITICAL ARCHITECTURAL ISOLATION RULE:
    Radiation telemetry is strictly classified as MISSION_CONTEXT / GENERAL_PHYSIOLOGICAL.
    It feeds directly to the RuleRegistry and Flight Surgeon decision support.
    It MUST NEVER be routed into physiological ML feature vectors, scalers, or classifiers.
    """

    @staticmethod
    def create_radiation_evidence_items(
        packet: SpaceEnvironmentPacket
    ) -> List[NormalizedEvidenceItem]:
        """Convert a SpaceEnvironmentPacket into normalized evidence items for the Evidence Registry."""
        ts = datetime.utcfromtimestamp(packet.timestamp_epoch_ms / 1000.0)

        # 1. Acute Absorbed Dose Rate Evidence Item
        dose_rate_item = NormalizedEvidenceItem(
            evidence_id=f"EV-RAD-DOSE-{uuid.uuid4().hex[:8].upper()}",
            source_agent="space_environment_subsystem",
            source_type=EvidenceSourceType.MISSION_CONTEXT,
            domain=RiskDomain.GENERAL_PHYSIOLOGICAL,
            metric_name="radiation_dose_rate_microgy_h",
            observed_value=float(packet.dose_rate_microgy_h),
            unit="µGy/h",
            timestamp=ts,
            observation_window="instantaneous_dosimetry",
            validity_status=EvidenceValidity.VALID,
            confidence=1.0,
            quality_status="CALIBRATED_ACTIVE",
            source_reference=f"DOSIMETER-PACKET-{packet.packet_id}",
            evidence_description=(
                f"Active space radiation absorbed dose rate is {packet.dose_rate_microgy_h:.2f} µGy/h "
                f"(Alert Level: {packet.alert_level}, SPE Active: {packet.spe_active})."
            ),
            is_confirmed=True,
            is_historical=False,
            evidence_classification="ENVIRONMENTAL_DOSIMETRY",
            is_eligible_for_risk=True,
            raw_context={
                "alert_level": packet.alert_level,
                "spe_active": packet.spe_active,
                "shielding_thickness_g_cm2": packet.shielding_thickness_g_cm2,
                "equivalent_dose_rate_msv_h": packet.equivalent_dose_rate_msv_h
            }
        )

        # 2. Cumulative Mission Dose Evidence Item
        cumulative_dose_item = NormalizedEvidenceItem(
            evidence_id=f"EV-RAD-CUM-{uuid.uuid4().hex[:8].upper()}",
            source_agent="space_environment_subsystem",
            source_type=EvidenceSourceType.MISSION_CONTEXT,
            domain=RiskDomain.GENERAL_PHYSIOLOGICAL,
            metric_name="radiation_cumulative_dose_msv",
            observed_value=float(packet.cumulative_mission_dose_msv),
            unit="mSv",
            timestamp=ts,
            observation_window="mission_cumulative",
            validity_status=EvidenceValidity.VALID,
            confidence=1.0,
            quality_status="CALIBRATED_ACTIVE",
            source_reference=f"DOSIMETER-PACKET-{packet.packet_id}",
            evidence_description=(
                f"Cumulative mission equivalent radiation dose is {packet.cumulative_mission_dose_msv:.2f} mSv "
                f"relative to NASA-STD-3001 limits."
            ),
            is_confirmed=True,
            is_historical=False,
            evidence_classification="ENVIRONMENTAL_DOSIMETRY",
            is_eligible_for_risk=True,
            raw_context={
                "cumulative_mission_dose_msv": packet.cumulative_mission_dose_msv,
                "shielding_thickness_g_cm2": packet.shielding_thickness_g_cm2
            }
        )

        return [dose_rate_item, cumulative_dose_item]

    @staticmethod
    def verify_ml_isolation(feature_columns: List[str]) -> bool:
        """Programmatic verification rule proving zero radiation features exist in ML feature list.

        Returns True if radiation parameters are strictly absent, False if violated.
        """
        forbidden_keywords = {"radiation", "dose_rate", "microgy", "msv", "spe_flux", "shielding"}
        for col in feature_columns:
            lowered = col.lower()
            for kw in forbidden_keywords:
                if kw in lowered:
                    return False
        return True
