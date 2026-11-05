"""Report builder service synthesizing JSON and markdown outputs."""
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, List, Optional, Any
from ..schemas.input_schema import AstronautHealthManifest
from ..schemas.signal_schema import SensorStreamData
from ..schemas.output_schema import (
    SensorQualityResult,
    OverallQuality,
    ProcessingDecision,
    SensorQualityReport
)
from ..explainability.explanation_engine import ExplanationEngine
from ..config.settings import get_settings

class ReportBuilder:
    """Constructs and validates the complete Sensor Quality Report."""

    def __init__(self, output_dir: Optional[Path] = None):
        cfg = get_settings()
        self.output_dir = Path(output_dir or cfg.output_dir).resolve()
        self.output_dir.mkdir(parents=True, exist_ok=True)
        self.explanation_engine = ExplanationEngine(cfg.visualizations_dir)

    def build_report(
        self,
        manifest: AstronautHealthManifest,
        streams: Dict[str, SensorStreamData],
        sensor_results: Dict[str, SensorQualityResult],
        overall_quality: OverallQuality,
        decision: ProcessingDecision,
        llm_explanation: Optional[Dict[str, Any]] = None,
        save_file: bool = True
    ) -> SensorQualityReport:
        viz_paths = self.explanation_engine.generate_all_diagnostics(streams, sensor_results)

        report = SensorQualityReport(
            agent="sensor_quality_agent",
            report_version="1.0",
            astronaut_id=manifest.metadata.astronaut_id,
            session_id=manifest.metadata.session_id,
            recording_id=manifest.metadata.recording_id,
            execution_timestamp=datetime.now(timezone.utc).isoformat(),
            overall_quality=overall_quality,
            sensors=sensor_results,
            processing_decision=decision,
            visualizations=viz_paths,
            llm_explanation=llm_explanation
        )

        if save_file:
            target_path = self.output_dir / "sensor_quality_report.json"
            with open(target_path, "w", encoding="utf-8") as f:
                json_str = report.model_dump_json(indent=2)
                f.write(json_str)

        return report
