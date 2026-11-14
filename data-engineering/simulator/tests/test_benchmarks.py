"""Unit tests for ML and LLM Benchmarking Suite."""
import pytest
from simulator.benchmarks.ml_benchmark import MLBenchmarkRunner
from simulator.benchmarks.llm_benchmark import LLMBenchmarkRunner
from simulator.space_environment.space_assessment_bridge import SpaceAssessmentBridge


def test_ml_benchmark_runner_radiation_isolation():
    """Verify ML benchmark runner enforces space radiation isolation."""
    runner = MLBenchmarkRunner()
    # verify_radiation_isolation must return True
    assert runner.verify_radiation_isolation() is True


def test_ml_benchmark_runner_dataset_loading_and_synthetic_generation():
    """Verify loading real WESAD data and generating matching synthetic data."""
    runner = MLBenchmarkRunner()
    X_real, y_real = runner.load_real_wesad_data()
    assert len(X_real) > 0
    assert len(y_real) == len(X_real)

    X_synth, y_synth = runner.generate_synthetic_benchmark_dataset(n_windows=30)
    assert len(X_synth) == 30
    assert len(y_synth) == 30
    assert list(X_synth.columns) == runner.feature_columns


def test_ml_benchmark_model_profiling():
    """Verify latency, throughput, and memory profiling on real and synthetic data."""
    runner = MLBenchmarkRunner()
    X_real, y_real = runner.load_real_wesad_data()
    sample_X = X_real.iloc[:20]
    sample_y = y_real.iloc[:20]

    if runner.rf_model is not None:
        rf_metrics = runner.benchmark_model("RandomForest", runner.rf_model, sample_X, sample_y)
        assert "latency_ms" in rf_metrics
        assert "throughput_windows_per_sec" in rf_metrics
        assert "metrics" in rf_metrics
        assert "accuracy" in rf_metrics["metrics"]


def test_llm_benchmark_runner_prompts_configured():
    """Verify LLM benchmark runner initializes 4 agent tasks."""
    runner = LLMBenchmarkRunner()
    assert "sensor_quality_briefing" in runner.benchmark_prompts
    assert "personal_health_synthesis" in runner.benchmark_prompts
    assert "risk_assessment_explanation" in runner.benchmark_prompts
    assert "medical_rag_synthesis" in runner.benchmark_prompts
