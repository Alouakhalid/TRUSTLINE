"""Diagnostic visualization and explanation generation engine."""
from pathlib import Path
from typing import List, Dict, Any, Optional
import numpy as np
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from ..schemas.signal_schema import SensorStreamData
from ..schemas.output_schema import DetectedIssue, SensorQualityResult

class ExplanationEngine:
    """Generates visual diagnostics and compiles explainability outputs."""

    def __init__(self, output_dir: Optional[Path] = None):
        self.output_dir = Path(output_dir or Path.cwd() / "data" / "output" / "visualizations").resolve()
        self.output_dir.mkdir(parents=True, exist_ok=True)

    def generate_sensor_diagnostic_plot(
        self,
        stream: SensorStreamData,
        result: SensorQualityResult,
        max_duration_sec: float = 30.0
    ) -> Path:
        samples_to_plot = min(stream.total_samples, int(max_duration_sec * stream.sampling_rate))
        time_vec = stream.timestamps[:samples_to_plot]
        data_vec = stream.data[:samples_to_plot]

        fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(10, 6), sharex=False)
        fig.suptitle(f"Sensor Diagnostic: {stream.sensor} (Status: {result.status.value})", fontsize=14, fontweight="bold")

        if data_vec.ndim > 1:
            for ch in range(data_vec.shape[1]):
                ax1.plot(time_vec, data_vec[:, ch], label=f"Axis {ch+1}", alpha=0.8)
            ax1.legend(loc="upper right")
        else:
            ax1.plot(time_vec, data_vec, color="tab:blue", lw=1.2, label=f"Raw {stream.sensor}")

        ax1.set_ylabel(f"Amplitude ({stream.unit})")
        ax1.set_title("Initial Signal Segment Telemetry")
        ax1.grid(True, linestyle="--", alpha=0.5)

        metric_names = [
            "Valid Ratio",
            "Timestamp",
            "Artifact-Free",
            "Noise Index",
            "Continuity"
        ]
        metric_values = [
            result.metrics.valid_sample_ratio,
            result.metrics.timestamp_integrity,
            1.0 - result.metrics.artifact_ratio,
            1.0 - result.metrics.noise_index,
            result.metrics.continuity_score
        ]

        colors = ["tab:green" if val >= 0.8 else "tab:orange" if val >= 0.6 else "tab:red" for val in metric_values]
        bars = ax2.bar(metric_names, metric_values, color=colors, alpha=0.85)
        ax2.set_ylim(0.0, 1.1)
        ax2.set_ylabel("Quality Score (0-1)")
        ax2.set_title("Component Quality Decomposition")
        ax2.grid(True, axis="y", linestyle="--", alpha=0.5)

        for bar, val in zip(bars, metric_values):
            yval = bar.get_height()
            ax2.text(bar.get_x() + bar.get_width()/2.0, yval + 0.02, f"{val:.2f}", ha="center", va="bottom", fontsize=9)

        plt.tight_layout()
        out_file = self.output_dir / f"diagnostic_{stream.sensor.lower()}.png"
        fig.savefig(str(out_file), dpi=150)
        plt.close(fig)
        return out_file

    def generate_all_diagnostics(
        self,
        streams: Dict[str, SensorStreamData],
        results: Dict[str, SensorQualityResult]
    ) -> List[str]:
        saved_plots = []
        for sensor_name, stream in streams.items():
            if sensor_name in results:
                path = self.generate_sensor_diagnostic_plot(stream, results[sensor_name])
                saved_plots.append(str(path))
        return saved_plots
