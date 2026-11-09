"""Service for ingesting and validating Sensor Quality Agent deliverables."""
import json
from pathlib import Path
from typing import Dict, List, Optional, Tuple, Any
import numpy as np
from ..config.settings import get_settings
from ..schemas.sensor_input import SensorIngestionContext, QuarantinedSensorInfo

class ValidatedSensorStream:
    """Read-only container for a validated physiological sensor array."""

    def __init__(
        self,
        sensor_name: str,
        data: np.ndarray,
        timestamps: np.ndarray,
        sampling_rate: float,
        unit: str,
        quality_score: float,
        status: str,
        warnings: List[str]
    ):
        self.sensor_name = sensor_name.upper()
        self._data = data
        self._timestamps = timestamps
        self.sampling_rate = float(sampling_rate)
        self.unit = unit
        self.quality_score = float(quality_score)
        self.status = status
        self.warnings = list(warnings)

    @property
    def data(self) -> np.ndarray:
        """Immutable read-only view of signal samples."""
        view = self._data.view()
        view.flags.writeable = False
        return view

    @property
    def timestamps(self) -> np.ndarray:
        """Immutable read-only view of signal timestamps."""
        view = self._timestamps.view()
        view.flags.writeable = False
        return view

    @property
    def duration_seconds(self) -> float:
        """Total duration computed from sample count and sampling frequency."""
        if self.sampling_rate <= 0:
            return 0.0
        return float(len(self._data)) / self.sampling_rate

class SensorIntegrationService:
    """Ingestion pipeline consuming Sensor Quality reports and loading biosignals."""

    def __init__(self, base_data_dir: Optional[Path] = None):
        cfg = get_settings()
        self.base_dir = base_data_dir or cfg.sensor_quality_dir / "data"

    def load_report(self, report_path_or_dict: Any) -> Dict[str, Any]:
        """Load report dictionary from file path, JSON string, or dict object."""
        if isinstance(report_path_or_dict, dict):
            return report_path_or_dict
        if isinstance(report_path_or_dict, (str, Path)):
            p = Path(report_path_or_dict).resolve()
            if not p.exists():
                candidate = Path(__file__).resolve().parent.parent.parent / "sensor_quality" / report_path_or_dict
                if candidate.exists():
                    p = candidate
            with open(p, "r", encoding="utf-8") as f:
                return json.load(f)
        if hasattr(report_path_or_dict, "model_dump"):
            return report_path_or_dict.model_dump()
        raise ValueError(f"Unsupported report payload format: {type(report_path_or_dict)}")

    def ingest_session(
        self,
        report_data: Any,
        manifest_data: Optional[Dict[str, Any]] = None
    ) -> Tuple[SensorIngestionContext, Dict[str, ValidatedSensorStream]]:
        """Validate Sensor Quality decisions, quarantine invalid sensors, and load valid streams."""
        rep = self.load_report(report_data)
        astronaut_id = rep.get("astronaut_id", "UNKNOWN")
        session_id = rep.get("session_id", "UNKNOWN")
        recording_id = rep.get("recording_id")
        overall = rep.get("overall_quality", {})
        decision = rep.get("processing_decision", {})

        overall_score = float(overall.get("score", 0.0))
        overall_status = str(overall.get("status", "INVALID"))
        can_proceed = bool(decision.get("can_proceed", False))
        upstream_warnings = list(decision.get("warnings", []))
        rejected_by_decision = set(decision.get("rejected_sensors", []))

        llm_briefing = None
        if "llm_explanation" in rep and rep["llm_explanation"]:
            llm_briefing = rep["llm_explanation"].get("briefing")

        sensors_dict = rep.get("sensors", {})
        valid_streams: Dict[str, ValidatedSensorStream] = {}
        valid_sensor_names: List[str] = []
        degraded_sensor_names: List[str] = []
        quarantined: List[QuarantinedSensorInfo] = []

        manifest_signals = {}
        if manifest_data:
            manifest_signals = manifest_data.get("signals", {})

        for s_name, s_info in sensors_dict.items():
            s_upper = s_name.upper()
            score = float(s_info.get("quality_score", 0.0))
            status = str(s_info.get("status", "INVALID"))
            rec = str(s_info.get("recommendation", "REJECT"))
            crit = bool(s_info.get("critical_failure", False))

            is_rejected = (
                s_upper in rejected_by_decision or
                rec == "REJECT" or
                crit or
                status == "INVALID" or
                score < 0.60
            )

            if is_rejected:
                quarantined.append(
                    QuarantinedSensorInfo(
                        sensor=s_upper,
                        rejection_reason=f"Status: {status}, Score: {score:.3f}, Critical: {crit}",
                        quality_score=score
                    )
                )
                continue

            s_warnings = []
            if status in ("ACCEPTABLE_WITH_WARNING", "DEGRADED"):
                degraded_sensor_names.append(s_upper)
                for iss in s_info.get("issues", []):
                    s_warnings.append(f"{iss.get('reason_code')}: {iss.get('explanation')}")
            else:
                valid_sensor_names.append(s_upper)

            sig_config = manifest_signals.get(s_name) or manifest_signals.get(s_upper) or {}
            raw_data, timestamps, fs, unit = self._load_sensor_arrays(s_upper, s_info, sig_config)

            if raw_data is not None and timestamps is not None:
                stream = ValidatedSensorStream(
                    sensor_name=s_upper,
                    data=raw_data,
                    timestamps=timestamps,
                    sampling_rate=fs,
                    unit=unit,
                    quality_score=score,
                    status=status,
                    warnings=s_warnings
                )
                valid_streams[s_upper] = stream
            else:
                quarantined.append(
                    QuarantinedSensorInfo(
                        sensor=s_upper,
                        rejection_reason="Failed to load underlying raw signal array",
                        quality_score=score
                    )
                )

        context = SensorIngestionContext(
            astronaut_id=astronaut_id,
            session_id=session_id,
            recording_id=recording_id,
            overall_quality_score=overall_score,
            overall_quality_status=overall_status,
            can_proceed=can_proceed,
            valid_sensors=valid_sensor_names,
            degraded_sensors=degraded_sensor_names,
            quarantined_sensors=quarantined,
            upstream_warnings=upstream_warnings,
            upstream_llm_briefing=llm_briefing
        )
        return context, valid_streams

    def _load_sensor_arrays(
        self,
        sensor_name: str,
        sensor_info: Dict[str, Any],
        sig_config: Dict[str, Any]
    ) -> Tuple[Optional[np.ndarray], Optional[np.ndarray], float, str]:
        """Load underlying binary numpy signal array and timestamp array."""
        fs = float(sig_config.get("sampling_rate") or sensor_info.get("sampling_rate", 700.0))
        unit = str(sig_config.get("unit", "unknown"))

        raw_file = sig_config.get("file")
        ts_file = sig_config.get("timestamp_file")

        if not raw_file:
            raw_file = f"raw_signals/{sensor_name}/{sensor_name.lower()}.npy"
        if not ts_file:
            ts_file = f"raw_signals/{sensor_name}/{sensor_name.lower()}_timestamps.npy"

        raw_path = (self.base_dir / raw_file).resolve()
        ts_path = (self.base_dir / ts_file).resolve()

        if not raw_path.exists():
            return None, None, fs, unit

        try:
            raw_arr = np.load(str(raw_path), mmap_mode="r")
            if raw_arr.ndim > 1 and raw_arr.shape[1] == 1:
                raw_arr = raw_arr.squeeze(axis=1)

            if ts_path.exists():
                ts_arr = np.load(str(ts_path), mmap_mode="r")
                if ts_arr.ndim > 1 and ts_arr.shape[1] == 1:
                    ts_arr = ts_arr.squeeze(axis=1)
            else:
                total_samples = len(raw_arr)
                ts_arr = np.arange(total_samples, dtype=np.float64) / fs

            return raw_arr, ts_arr, fs, unit
        except Exception:
            return None, None, fs, unit
