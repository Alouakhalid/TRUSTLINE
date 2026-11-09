"""Independent Input Validator auditing manifests, raw signals, and timestamps."""
from pathlib import Path
from typing import List, Dict, Any, Optional
import numpy as np
try:
    from .schemas import ValidationCheckResult, CheckStatus
except ImportError:
    try:
        from schemas import ValidationCheckResult, CheckStatus
    except ImportError:
        from validation.schemas import ValidationCheckResult, CheckStatus

class InputValidator:
    """Performs rigorous, non-destructive validation of input manifest and raw arrays."""

    VALID_SENSORS = {"ECG", "EDA", "RESP", "EMG", "ACC", "TEMP"}
    VALID_UNITS = {
        "ECG": {"mV", "V", "uV"},
        "EDA": {"uS", "mS", "nS"},
        "RESP": {"mV", "V", "%", "breaths/min"},
        "EMG": {"mV", "V", "uV"},
        "ACC": {"g", "m/s^2", "m/s2"},
        "TEMP": {"C", "degC", "F", "K"}
    }

    def __init__(self, base_dir: Optional[Path] = None):
        self.base_dir = Path(base_dir or Path.cwd()).resolve()

    def validate_manifest_dict(self, manifest_dict: Dict[str, Any]) -> List[ValidationCheckResult]:
        checks: List[ValidationCheckResult] = []

        meta = manifest_dict.get("metadata")
        if not isinstance(meta, dict):
            checks.append(ValidationCheckResult(
                check_id="INPUT-META-001",
                category="INPUT_VALIDATION",
                target="METADATA",
                status=CheckStatus.FAILED,
                message="Manifest metadata missing or not a dictionary.",
                evidence={"received_type": type(meta).__name__}
            ))
            return checks

        ast_id = meta.get("astronaut_id")
        sess_id = meta.get("session_id")

        if not ast_id or not isinstance(ast_id, str):
            checks.append(ValidationCheckResult(
                check_id="INPUT-META-002",
                category="INPUT_VALIDATION",
                target="astronaut_id",
                status=CheckStatus.FAILED,
                message="Required field 'astronaut_id' is missing, empty, or non-string."
            ))
        else:
            checks.append(ValidationCheckResult(
                check_id="INPUT-META-002",
                category="INPUT_VALIDATION",
                target="astronaut_id",
                status=CheckStatus.PASSED,
                message=f"Valid astronaut identifier: {ast_id}",
                evidence={"astronaut_id": ast_id}
            ))

        if not sess_id or not isinstance(sess_id, str):
            checks.append(ValidationCheckResult(
                check_id="INPUT-META-003",
                category="INPUT_VALIDATION",
                target="session_id",
                status=CheckStatus.FAILED,
                message="Required field 'session_id' is missing, empty, or non-string."
            ))
        else:
            checks.append(ValidationCheckResult(
                check_id="INPUT-META-003",
                category="INPUT_VALIDATION",
                target="session_id",
                status=CheckStatus.PASSED,
                message=f"Valid session identifier: {sess_id}",
                evidence={"session_id": sess_id}
            ))

        signals = manifest_dict.get("signals")
        if not isinstance(signals, dict) or len(signals) == 0:
            checks.append(ValidationCheckResult(
                check_id="INPUT-SIGNALS-001",
                category="INPUT_VALIDATION",
                target="SIGNALS",
                status=CheckStatus.FAILED,
                message="Signals dictionary is missing or empty."
            ))
            return checks

        for sensor_name, config in signals.items():
            checks.extend(self.validate_sensor_config(sensor_name, config))

        return checks

    def validate_sensor_config(self, sensor_name: str, config: Dict[str, Any]) -> List[ValidationCheckResult]:
        checks: List[ValidationCheckResult] = []
        target = sensor_name.upper()

        if target not in self.VALID_SENSORS:
            checks.append(ValidationCheckResult(
                check_id="INPUT-SENSOR-UNSUPPORTED",
                category="INPUT_VALIDATION",
                target=target,
                status=CheckStatus.FAILED,
                message=f"Sensor '{sensor_name}' is not an approved modality ({self.VALID_SENSORS})."
            ))
            return checks

        fs = config.get("sampling_rate")
        if not isinstance(fs, (int, float)) or fs <= 0.0:
            checks.append(ValidationCheckResult(
                check_id="INPUT-FS-INVALID",
                category="INPUT_VALIDATION",
                target=target,
                status=CheckStatus.FAILED,
                message=f"Sampling frequency must be positive numeric, received: {fs}",
                evidence={"sampling_rate": fs}
            ))
        else:
            checks.append(ValidationCheckResult(
                check_id="INPUT-FS-VALID",
                category="INPUT_VALIDATION",
                target=target,
                status=CheckStatus.PASSED,
                message=f"Valid sampling rate: {fs} Hz",
                evidence={"sampling_rate": fs}
            ))

        unit = config.get("unit")
        allowed_units = self.VALID_UNITS.get(target, set())
        if not unit or unit not in allowed_units:
            checks.append(ValidationCheckResult(
                check_id="INPUT-UNIT-INVALID",
                category="INPUT_VALIDATION",
                target=target,
                status=CheckStatus.WARNING,
                message=f"Sensor unit '{unit}' outside standard physical set {allowed_units}.",
                evidence={"unit": unit, "expected": list(allowed_units)}
            ))
        else:
            checks.append(ValidationCheckResult(
                check_id="INPUT-UNIT-VALID",
                category="INPUT_VALIDATION",
                target=target,
                status=CheckStatus.PASSED,
                message=f"Approved unit of measurement: {unit}",
                evidence={"unit": unit}
            ))

        file_path_str = config.get("file")
        if not file_path_str:
            checks.append(ValidationCheckResult(
                check_id="INPUT-FILE-MISSING",
                category="INPUT_VALIDATION",
                target=target,
                status=CheckStatus.FAILED,
                message="Signal file path is not specified."
            ))
            return checks

        if ".." in str(file_path_str).split("/") or str(file_path_str).startswith("/"):
            checks.append(ValidationCheckResult(
                check_id="INPUT-PATH-TRAVERSAL",
                category="INPUT_VALIDATION",
                target=target,
                status=CheckStatus.FAILED,
                message=f"Path traversal detected in signal file path: {file_path_str}",
                evidence={"file": file_path_str}
            ))
            return checks

        resolved_data_path = (self.base_dir / file_path_str).resolve()
        if not resolved_data_path.exists():
            checks.append(ValidationCheckResult(
                check_id="INPUT-FILE-NOT-FOUND",
                category="INPUT_VALIDATION",
                target=target,
                status=CheckStatus.FAILED,
                message=f"Signal file does not exist on disk: {resolved_data_path}",
                evidence={"resolved_path": str(resolved_data_path)}
            ))
            return checks

        checks.append(ValidationCheckResult(
            check_id="INPUT-FILE-EXISTS",
            category="INPUT_VALIDATION",
            target=target,
            status=CheckStatus.PASSED,
            message="Signal file located and readable.",
            evidence={"file": str(resolved_data_path)}
        ))

        try:
            arr = np.load(str(resolved_data_path), mmap_mode="r")
            checks.extend(self.validate_raw_array(target, arr))
        except Exception as exc:
            checks.append(ValidationCheckResult(
                check_id="INPUT-FILE-READ-ERROR",
                category="INPUT_VALIDATION",
                target=target,
                status=CheckStatus.FAILED,
                message=f"Failed to read signal array file: {str(exc)}",
                evidence={"exception": str(exc)}
            ))
            return checks

        ts_file_str = config.get("timestamp_file")
        if ts_file_str:
            resolved_ts_path = (self.base_dir / ts_file_str).resolve()
            if not resolved_ts_path.exists():
                checks.append(ValidationCheckResult(
                    check_id="INPUT-TS-FILE-NOT-FOUND",
                    category="INPUT_VALIDATION",
                    target=target,
                    status=CheckStatus.FAILED,
                    message=f"Timestamp file does not exist: {resolved_ts_path}"
                ))
            else:
                try:
                    ts_arr = np.load(str(resolved_ts_path), mmap_mode="r")
                    checks.extend(self.validate_timestamps(target, ts_arr, len(arr), float(fs)))
                except Exception as exc:
                    checks.append(ValidationCheckResult(
                        check_id="INPUT-TS-READ-ERROR",
                        category="INPUT_VALIDATION",
                        target=target,
                        status=CheckStatus.FAILED,
                        message=f"Failed to read timestamp array: {str(exc)}"
                    ))

        return checks

    def validate_raw_array(self, sensor: str, arr: np.ndarray) -> List[ValidationCheckResult]:
        checks: List[ValidationCheckResult] = []

        if arr.size == 0 or len(arr) == 0:
            checks.append(ValidationCheckResult(
                check_id="INPUT-ARRAY-EMPTY",
                category="INPUT_VALIDATION",
                target=sensor,
                status=CheckStatus.FAILED,
                message="Signal array has zero samples.",
                evidence={"samples": 0}
            ))
            return checks

        if not np.issubdtype(arr.dtype, np.number):
            checks.append(ValidationCheckResult(
                check_id="INPUT-DTYPE-NON-NUMERIC",
                category="INPUT_VALIDATION",
                target=sensor,
                status=CheckStatus.FAILED,
                message=f"Signal array dtype is non-numeric: {arr.dtype}",
                evidence={"dtype": str(arr.dtype)}
            ))
            return checks

        checks.append(ValidationCheckResult(
            check_id="INPUT-ARRAY-VALID",
            category="INPUT_VALIDATION",
            target=sensor,
            status=CheckStatus.PASSED,
            message=f"Signal array valid. Samples: {len(arr)}, Dtype: {arr.dtype}, Shape: {arr.shape}",
            evidence={"samples": len(arr), "shape": list(arr.shape), "dtype": str(arr.dtype)}
        ))

        nan_count = int(np.sum(np.isnan(arr) | np.isinf(arr)))
        if nan_count > 0:
            nan_ratio = float(nan_count) / float(arr.size)
            checks.append(ValidationCheckResult(
                check_id="INPUT-ARRAY-NAN-INF",
                category="INPUT_VALIDATION",
                target=sensor,
                status=CheckStatus.FAILED if nan_ratio > 0.05 else CheckStatus.WARNING,
                message=f"Detected {nan_count} NaN or Inf values ({nan_ratio:.2%}).",
                evidence={"nan_count": nan_count, "nan_ratio": nan_ratio}
            ))

        return checks

    def validate_timestamps(
        self,
        sensor: str,
        timestamps: np.ndarray,
        expected_len: int,
        sampling_rate: float
    ) -> List[ValidationCheckResult]:
        checks: List[ValidationCheckResult] = []

        if len(timestamps) != expected_len:
            checks.append(ValidationCheckResult(
                check_id="INPUT-TS-LEN-MISMATCH",
                category="INPUT_VALIDATION",
                target=sensor,
                status=CheckStatus.FAILED,
                message=f"Timestamp length ({len(timestamps)}) does not match signal sample count ({expected_len}).",
                evidence={"ts_len": len(timestamps), "signal_len": expected_len}
            ))
            return checks

        if len(timestamps) < 2:
            return checks

        diffs = np.diff(timestamps)
        backwards = np.where(diffs < 0.0)[0]
        if len(backwards) > 0:
            checks.append(ValidationCheckResult(
                check_id="INPUT-TS-BACKWARDS",
                category="INPUT_VALIDATION",
                target=sensor,
                status=CheckStatus.FAILED,
                message=f"Non-monotonic timestamps detected ({len(backwards)} backwards steps).",
                evidence={"backwards_count": len(backwards), "first_index": int(backwards[0])}
            ))

        duplicates = np.where(diffs == 0.0)[0]
        if len(duplicates) > 0:
            checks.append(ValidationCheckResult(
                check_id="INPUT-TS-DUPLICATES",
                category="INPUT_VALIDATION",
                target=sensor,
                status=CheckStatus.FAILED if len(duplicates) > 10 else CheckStatus.WARNING,
                message=f"Duplicate timestamps detected ({len(duplicates)} occurrences).",
                evidence={"duplicate_count": len(duplicates)}
            ))

        nominal_dt = 1.0 / sampling_rate if sampling_rate > 0 else 0.0
        gap_indices = np.where(diffs > nominal_dt * 2.5)[0]
        if len(gap_indices) > 0:
            max_gap = float(np.max(diffs[gap_indices]))
            checks.append(ValidationCheckResult(
                check_id="INPUT-TS-GAPS",
                category="INPUT_VALIDATION",
                target=sensor,
                status=CheckStatus.WARNING,
                message=f"Timestamp gaps detected ({len(gap_indices)} gaps, max gap: {max_gap:.4f}s).",
                evidence={"gap_count": len(gap_indices), "max_gap_seconds": max_gap}
            ))

        return checks
