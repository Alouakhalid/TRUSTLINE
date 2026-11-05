"""LangChain inspection tools for sensor quality analysis."""
from typing import Dict, Any, Optional
import json
import numpy as np
from langchain_core.tools import tool
from ..core.integrity_checks import IntegrityChecker
from ..core.temporal_checks import TemporalChecker
from ..core.noise_analysis import NoiseAnalyzer
from ..core.artifact_detection import ArtifactDetector
from ..core.flatline_detection import FlatlineDetector
from ..core.sensor_validation import SensorValidator
from ..core.quality_scoring import QualityScorer
from ..schemas.signal_schema import SensorStreamData, SensorType
from ..storage.signal_store import SignalStore

global_tool_store = SignalStore()

def get_tool_store() -> SignalStore:
    return global_tool_store

@tool
def inspect_signal_integrity(sensor_name: str) -> str:
    """Inspects missing samples, NaNs, Infs, and array dtypes for a stored sensor signal."""
    stream = global_tool_store.get_stream(sensor_name)
    if stream is None:
        return json.dumps({"error": f"Sensor '{sensor_name}' not found in active signal store."})
    checker = IntegrityChecker()
    valid_ratio, nan_ratio, issues = checker.check_integrity(stream)
    return json.dumps({
        "sensor": sensor_name,
        "valid_sample_ratio": round(valid_ratio, 4),
        "missing_sample_ratio": round(nan_ratio, 4),
        "issue_count": len(issues),
        "issues": [iss.model_dump() for iss in issues]
    })

@tool
def inspect_temporal_integrity(sensor_name: str) -> str:
    """Verifies timestamp consistency, gaps, backwards timestamps, and sampling jitter."""
    stream = global_tool_store.get_stream(sensor_name)
    if stream is None:
        return json.dumps({"error": f"Sensor '{sensor_name}' not found in active signal store."})
    checker = TemporalChecker()
    ts_integrity, continuity, issues = checker.check_temporal_integrity(stream)
    return json.dumps({
        "sensor": sensor_name,
        "timestamp_integrity": round(ts_integrity, 4),
        "continuity_score": round(continuity, 4),
        "issue_count": len(issues),
        "issues": [iss.model_dump() for iss in issues]
    })

@tool
def analyze_signal_noise(sensor_name: str) -> str:
    """Analyzes powerline interference, baseline wander, and high-frequency noise."""
    stream = global_tool_store.get_stream(sensor_name)
    if stream is None:
        return json.dumps({"error": f"Sensor '{sensor_name}' not found in active signal store."})
    analyzer = NoiseAnalyzer()
    noise_index, issues = analyzer.analyze_noise(stream)
    return json.dumps({
        "sensor": sensor_name,
        "noise_index": round(noise_index, 4),
        "issue_count": len(issues),
        "issues": [iss.model_dump() for iss in issues]
    })

@tool
def detect_signal_artifacts(sensor_name: str) -> str:
    """Detects amplifier saturation, clipping, and sudden high-amplitude spikes."""
    stream = global_tool_store.get_stream(sensor_name)
    if stream is None:
        return json.dumps({"error": f"Sensor '{sensor_name}' not found in active signal store."})
    detector = ArtifactDetector()
    art_ratio, sat_ratio, issues = detector.detect_artifacts(stream)
    return json.dumps({
        "sensor": sensor_name,
        "artifact_ratio": round(art_ratio, 4),
        "saturation_ratio": round(sat_ratio, 4),
        "issue_count": len(issues),
        "issues": [iss.model_dump() for iss in issues]
    })

@tool
def detect_flatline_segments(sensor_name: str) -> str:
    """Identifies frozen sensors, near-zero variance runs, and disconnected leads."""
    stream = global_tool_store.get_stream(sensor_name)
    if stream is None:
        return json.dumps({"error": f"Sensor '{sensor_name}' not found in active signal store."})
    detector = FlatlineDetector()
    flat_ratio, issues = detector.detect_flatline(stream)
    return json.dumps({
        "sensor": sensor_name,
        "flatline_ratio": round(flat_ratio, 4),
        "issue_count": len(issues),
        "issues": [iss.model_dump() for iss in issues]
    })

@tool
def validate_sensor_signal(sensor_name: str) -> str:
    """Checks whether sensor measurements stay within technical operational ranges."""
    stream = global_tool_store.get_stream(sensor_name)
    if stream is None:
        return json.dumps({"error": f"Sensor '{sensor_name}' not found in active signal store."})
    validator = SensorValidator()
    is_valid, issues = validator.validate_sensor(stream)
    return json.dumps({
        "sensor": sensor_name,
        "is_technically_valid": is_valid,
        "issue_count": len(issues),
        "issues": [iss.model_dump() for iss in issues]
    })

@tool
def calculate_signal_quality(sensor_name: str) -> str:
    """Computes calibrated overall quality score and status for a sensor stream."""
    stream = global_tool_store.get_stream(sensor_name)
    if stream is None:
        return json.dumps({"error": f"Sensor '{sensor_name}' not found in active signal store."})
    from ..core.quality_engine import QualityEngine
    engine = QualityEngine()
    result = engine.inspect_stream(stream)
    return result.model_dump_json(indent=2)

@tool
def generate_quality_explanation(sensor_name: str) -> str:
    """Generates structured deterministic technical explanation for flagged issues."""
    stream = global_tool_store.get_stream(sensor_name)
    if stream is None:
        return json.dumps({"error": f"Sensor '{sensor_name}' not found in active signal store."})
    from ..core.quality_engine import QualityEngine
    engine = QualityEngine()
    result = engine.inspect_stream(stream)
    explanations = []
    for issue in result.issues:
        explanations.append({
            "reason_code": issue.reason_code,
            "severity": issue.severity.value,
            "explanation": issue.explanation,
            "recommended_handling": issue.recommended_handling,
            "evidence": [e.model_dump() for e in issue.evidence]
        })
    return json.dumps({
        "sensor": sensor_name,
        "quality_score": result.quality_score,
        "status": result.status.value,
        "recommendation": result.recommendation,
        "explanations": explanations
    }, indent=2)
