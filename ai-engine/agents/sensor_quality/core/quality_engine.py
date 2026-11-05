"""Core quality engine orchestrator."""
from typing import Dict, List, Tuple
from ..schemas.signal_schema import SensorStreamData
from ..schemas.output_schema import (
    SensorQualityMetrics,
    SensorQualityResult,
    OverallQuality,
    ProcessingDecision
)
from .integrity_checks import IntegrityChecker
from .temporal_checks import TemporalChecker
from .noise_analysis import NoiseAnalyzer
from .artifact_detection import ArtifactDetector
from .flatline_detection import FlatlineDetector
from .sensor_validation import SensorValidator
from .quality_scoring import QualityScorer

class QualityEngine:
    """Orchestrates comprehensive signal inspection pipelines across all biosensors."""

    def __init__(self):
        self.integrity_checker = IntegrityChecker()
        self.temporal_checker = TemporalChecker()
        self.noise_analyzer = NoiseAnalyzer()
        self.artifact_detector = ArtifactDetector()
        self.flatline_detector = FlatlineDetector()
        self.sensor_validator = SensorValidator()
        self.quality_scorer = QualityScorer()

    def inspect_stream(self, stream: SensorStreamData) -> SensorQualityResult:
        all_issues = []

        valid_ratio, missing_ratio, integrity_issues = self.integrity_checker.check_integrity(stream)
        all_issues.extend(integrity_issues)

        ts_integrity, continuity_score, temporal_issues = self.temporal_checker.check_temporal_integrity(stream)
        all_issues.extend(temporal_issues)

        flatline_ratio, flatline_issues = self.flatline_detector.detect_flatline(stream)
        all_issues.extend(flatline_issues)

        artifact_ratio, saturation_ratio, artifact_issues = self.artifact_detector.detect_artifacts(stream)
        all_issues.extend(artifact_issues)

        noise_index, noise_issues = self.noise_analyzer.analyze_noise(stream)
        all_issues.extend(noise_issues)

        is_plausible, validation_issues = self.sensor_validator.validate_sensor(stream)
        all_issues.extend(validation_issues)

        metrics = SensorQualityMetrics(
            valid_sample_ratio=round(float(valid_ratio), 4),
            missing_sample_ratio=round(float(missing_ratio), 4),
            artifact_ratio=round(float(artifact_ratio), 4),
            flatline_ratio=round(float(flatline_ratio), 4),
            noise_index=round(float(noise_index), 4),
            timestamp_integrity=round(float(ts_integrity), 4),
            saturation_ratio=round(float(saturation_ratio), 4),
            continuity_score=round(float(continuity_score), 4)
        )

        return self.quality_scorer.score_sensor(
            sensor=stream.sensor,
            metrics=metrics,
            issues=all_issues,
            sampling_rate=stream.sampling_rate,
            total_samples=stream.total_samples,
            duration_seconds=stream.duration_seconds
        )

    def inspect_all_streams(self, streams: Dict[str, SensorStreamData]) -> Tuple[Dict[str, SensorQualityResult], OverallQuality, ProcessingDecision]:
        results: Dict[str, SensorQualityResult] = {}
        for sensor_name, stream in streams.items():
            results[sensor_name] = self.inspect_stream(stream)

        overall = self.quality_scorer.score_overall_session(results)

        rejected_sensors = [s for s, res in results.items() if res.recommendation == "REJECT"]
        warnings = []
        for s, res in results.items():
            for iss in res.issues:
                warnings.append(f"[{s}] {iss.reason_code}: {iss.explanation}")

        can_proceed = len(rejected_sensors) < (len(streams) / 2.0) and overall.score >= 0.50

        decision = ProcessingDecision(
            can_proceed=can_proceed,
            warnings=warnings[:10],
            rejected_sensors=rejected_sensors,
            next_agent="personal_health_agent" if can_proceed else None
        )

        return results, overall, decision
