"""CrewAI tool adapters for sensor quality agent."""
from typing import List, Any
from crewai.tools import tool
from .langchain_tools import (
    inspect_signal_integrity,
    inspect_temporal_integrity,
    analyze_signal_noise,
    detect_signal_artifacts,
    detect_flatline_segments,
    validate_sensor_signal,
    calculate_signal_quality,
    generate_quality_explanation
)

@tool("Inspect Signal Integrity")
def crew_inspect_integrity(sensor_name: str) -> str:
    """Inspects missing samples, NaNs, Infs, and array dtypes for a sensor."""
    return inspect_signal_integrity.invoke({"sensor_name": sensor_name})

@tool("Inspect Temporal Integrity")
def crew_inspect_temporal(sensor_name: str) -> str:
    """Verifies timestamp consistency, gaps, backwards timestamps, and jitter."""
    return inspect_temporal_integrity.invoke({"sensor_name": sensor_name})

@tool("Analyze Signal Noise")
def crew_analyze_noise(sensor_name: str) -> str:
    """Analyzes powerline interference, baseline wander, and high-frequency noise."""
    return analyze_signal_noise.invoke({"sensor_name": sensor_name})

@tool("Detect Signal Artifacts")
def crew_detect_artifacts(sensor_name: str) -> str:
    """Detects amplifier saturation, clipping, and sudden high-amplitude spikes."""
    return detect_signal_artifacts.invoke({"sensor_name": sensor_name})

@tool("Detect Flatline Segments")
def crew_detect_flatline(sensor_name: str) -> str:
    """Identifies frozen sensors, near-zero variance runs, and disconnections."""
    return detect_flatline_segments.invoke({"sensor_name": sensor_name})

@tool("Validate Sensor Signal")
def crew_validate_sensor(sensor_name: str) -> str:
    """Checks whether sensor measurements stay within technical operational ranges."""
    return validate_sensor_signal.invoke({"sensor_name": sensor_name})

@tool("Calculate Signal Quality")
def crew_calculate_quality(sensor_name: str) -> str:
    """Computes calibrated overall quality score and status for a sensor stream."""
    return calculate_signal_quality.invoke({"sensor_name": sensor_name})

@tool("Generate Quality Explanation")
def crew_generate_explanation(sensor_name: str) -> str:
    """Generates structured deterministic technical explanation for flagged issues."""
    return generate_quality_explanation.invoke({"sensor_name": sensor_name})

def get_crewai_tools() -> List[Any]:
    return [
        crew_inspect_integrity,
        crew_inspect_temporal,
        crew_analyze_noise,
        crew_detect_artifacts,
        crew_detect_flatline,
        crew_validate_sensor,
        crew_calculate_quality,
        crew_generate_explanation
    ]
