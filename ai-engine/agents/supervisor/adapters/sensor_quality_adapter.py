"""Sensor Quality Agent adapter invoking deterministic signal inspection engine."""
import json
from pathlib import Path
from typing import Dict, Any, Tuple
from .base import BaseAgentAdapter
from ..schemas.assessment import AgentExecutionState, AgentExecutionStatus
from ..config.settings import get_supervisor_settings

class SensorQualityAdapter(BaseAgentAdapter):
    """Adapter invoking Sensor Quality Agent pipeline and mapping outputs to state."""

    def __init__(self):
        super().__init__(agent_name="sensor_quality_agent")

    def run(self, state: Dict[str, Any]) -> Tuple[Dict[str, Any], AgentExecutionStatus]:
        cfg = get_supervisor_settings()
        existing = state.get("sensor_quality_result")
        if existing is not None:
            status = AgentExecutionStatus(
                agent_name=self.agent_name,
                status=AgentExecutionState.SUCCESS,
                warnings=["Used pre-existing Sensor Quality report from state."]
            )
            return {"sensor_quality_result": existing}, status

        manifest_path = state.get("manifest_path")
        raw_manifest = state.get("sensor_data") or state.get("raw_manifest")

        from sensor_quality.schemas.input_schema import AstronautHealthManifest
        from sensor_quality.ingestion.signal_loader import SignalLoader
        from sensor_quality.core.quality_engine import QualityEngine
        from sensor_quality.services.report_builder import ReportBuilder

        manifest_obj = None
        base_dir = None

        if manifest_path:
            m_path = Path(manifest_path).resolve()
            if not m_path.exists():
                candidate = cfg.sensor_quality_dir / manifest_path
                if candidate.exists():
                    m_path = candidate
            if m_path.exists():
                with open(m_path, "r", encoding="utf-8") as f:
                    manifest_data = json.load(f)
                manifest_obj = AstronautHealthManifest.model_validate(manifest_data)
                base_dir = m_path.parent.parent
            else:
                status = AgentExecutionStatus(
                    agent_name=self.agent_name,
                    status=AgentExecutionState.FAILED,
                    error_message=f"Manifest file not found: {manifest_path}",
                    warnings=[f"Sensor telemetry unavailable: manifest {manifest_path} could not be resolved."]
                )
                return {}, status
        elif raw_manifest:
            manifest_obj = AstronautHealthManifest.model_validate(raw_manifest)
            base_dir = cfg.sensor_quality_dir / "data"
        else:
            status = AgentExecutionStatus(
                agent_name=self.agent_name,
                status=AgentExecutionState.SKIPPED,
                warnings=["No sensor manifest supplied; skipping sensor quality inspection."]
            )
            return {}, status

        loader = SignalLoader(base_dir=base_dir)
        streams = loader.load_all_sensors(manifest_obj, mmap=True)

        engine = QualityEngine()
        sensor_results, overall_quality, decision = engine.inspect_all_streams(streams)

        builder = ReportBuilder(output_dir=cfg.output_dir)
        report = builder.build_report(
            manifest=manifest_obj,
            streams=streams,
            sensor_results=sensor_results,
            overall_quality=overall_quality,
            decision=decision,
            save_file=True
        )

        exec_state = AgentExecutionState.SUCCESS if decision.can_proceed else AgentExecutionState.PARTIAL
        warnings = list(decision.warnings)
        if not decision.can_proceed:
            warnings.append("Sensor quality gating rejected telemetry from proceeding nominal downstream.")

        status = AgentExecutionStatus(
            agent_name=self.agent_name,
            status=exec_state,
            warnings=warnings
        )

        return {
            "sensor_quality_result": report.model_dump(),
            "sensor_quality_report": report.model_dump()
        }, status
