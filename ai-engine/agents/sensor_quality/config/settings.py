"""Settings and configuration for Sensor Quality Agent."""
import os
from pathlib import Path
from typing import Dict, List
from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict

class SensorQualitySettings(BaseSettings):
    """Application settings for Sensor Quality Agent."""
    model_config = SettingsConfigDict(
        env_file=str(Path(__file__).resolve().parent.parent / ".env"),
        env_file_encoding="utf-8",
        extra="ignore"
    )

    groq_api_key: str = Field(default="", alias="GROQ_API_KEY")
    groq_model: str = Field(default="qwen/qwen3.8-27b", alias="GROQ_MODEL")
    sensor_quality_log_level: str = Field(default="INFO", alias="SENSOR_QUALITY_LOG_LEVEL")

    default_sampling_rates: Dict[str, float] = {
        "ECG": 700.0,
        "EDA": 4.0,
        "RESP": 700.0,
        "EMG": 700.0,
        "ACC": 700.0,
        "TEMP": 700.0
    }

    flatline_variance_threshold: float = 1e-6
    flatline_min_duration_seconds: float = 3.0
    max_acceptable_nan_ratio: float = 0.05
    critical_nan_ratio: float = 0.20
    max_timestamp_jitter_ratio: float = 0.10
    spike_zscore_threshold: float = 4.5
    temp_max_rate_of_change: float = 0.5
    powerline_frequencies: List[float] = [50.0, 60.0]

    component_weights: Dict[str, float] = {
        "valid_sample_ratio": 0.30,
        "timestamp_integrity": 0.25,
        "artifact_free_ratio": 0.20,
        "noise_score": 0.15,
        "continuity_score": 0.10
    }

    base_dir: Path = Path(__file__).resolve().parent.parent
    data_dir: Path = Path(__file__).resolve().parent.parent / "data"
    output_dir: Path = Path(__file__).resolve().parent.parent / "data" / "output"
    visualizations_dir: Path = Path(__file__).resolve().parent.parent / "data" / "output" / "visualizations"

settings = SensorQualitySettings()

def get_settings() -> SensorQualitySettings:
    """Return the global settings instance."""
    return settings
