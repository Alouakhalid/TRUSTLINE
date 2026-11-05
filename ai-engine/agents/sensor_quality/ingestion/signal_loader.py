"""Memory-conscious raw physiological signal loader."""
import os
from pathlib import Path
from typing import Dict, Optional, Tuple, Generator
import numpy as np
from ..schemas.input_schema import AstronautHealthManifest, SensorSignalConfig
from ..schemas.signal_schema import SensorStreamData, SignalWindow

class SignalLoader:
    """Robust, memory-efficient loader for multi-rate physiological signals."""

    def __init__(self, base_dir: Optional[Path] = None):
        self.base_dir = Path(base_dir or Path.cwd()).resolve()

    def _resolve_safe_path(self, relative_path: str) -> Path:
        target = (self.base_dir / relative_path).resolve()
        try:
            target.relative_to(self.base_dir)
        except ValueError:
            raise PermissionError(f"Path traversal detected and rejected: {relative_path}")
        if not target.exists():
            raise FileNotFoundError(f"Signal file does not exist: {target}")
        return target

    def load_sensor_stream(
        self,
        sensor_name: str,
        config: SensorSignalConfig,
        mmap: bool = True
    ) -> SensorStreamData:
        data_path = self._resolve_safe_path(config.file)
        mmap_mode = "r" if mmap else None

        raw_array = np.load(str(data_path), mmap_mode=mmap_mode)
        if raw_array.ndim > 1 and raw_array.shape[1] == 1:
            raw_array = raw_array.squeeze(axis=1)

        total_samples = len(raw_array)
        sampling_rate = float(config.sampling_rate)
        duration = float(total_samples) / sampling_rate if sampling_rate > 0 else 0.0

        if config.timestamp_file:
            ts_path = self._resolve_safe_path(config.timestamp_file)
            timestamps = np.load(str(ts_path), mmap_mode=mmap_mode)
            if timestamps.ndim > 1 and timestamps.shape[1] == 1:
                timestamps = timestamps.squeeze(axis=1)
        else:
            timestamps = np.arange(total_samples, dtype=np.float64) / sampling_rate

        return SensorStreamData(
            sensor=sensor_name,
            sampling_rate=sampling_rate,
            unit=config.unit,
            data=raw_array,
            timestamps=timestamps,
            duration_seconds=duration,
            total_samples=total_samples
        )

    def load_all_sensors(
        self,
        manifest: AstronautHealthManifest,
        mmap: bool = True
    ) -> Dict[str, SensorStreamData]:
        loaded = {}
        for sensor_name, config in manifest.signals.items():
            loaded[sensor_name] = self.load_sensor_stream(sensor_name, config, mmap=mmap)
        return loaded

    def create_sliding_windows(
        self,
        stream: SensorStreamData,
        window_duration_sec: float = 60.0,
        step_duration_sec: float = 30.0
    ) -> Generator[SignalWindow, None, None]:
        window_size = int(round(window_duration_sec * stream.sampling_rate))
        step_size = int(round(step_duration_sec * stream.sampling_rate))

        if window_size <= 0 or step_size <= 0:
            raise ValueError("Window size and step size must be positive")

        total = stream.total_samples
        idx = 0
        window_counter = 0

        while idx + window_size <= total:
            w_data = stream.data[idx : idx + window_size]
            w_ts = stream.timestamps[idx : idx + window_size]
            yield SignalWindow(
                sensor=stream.sensor,
                window_index=window_counter,
                start_time=float(w_ts[0]),
                end_time=float(w_ts[-1]),
                sampling_rate=stream.sampling_rate,
                data=w_data,
                timestamps=w_ts
            )
            idx += step_size
            window_counter += 1
