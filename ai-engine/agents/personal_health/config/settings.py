"""Settings and runtime configuration for Personal Health Agent."""
import os
from pathlib import Path
from typing import Dict, List, Optional
from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict

class PersonalHealthSettings(BaseSettings):
    """Configuration settings for Personal Health Agent."""
    model_config = SettingsConfigDict(
        env_file=str(Path(__file__).resolve().parent.parent / ".env"),
        env_file_encoding="utf-8",
        extra="ignore"
    )

    groq_api_key: str = Field(default="", alias="GROQ_API_KEY")
    groq_chat_model: str = Field(default="qwen/qwen3.8-27b", alias="GROQ_CHAT_MODEL")
    groq_whisper_model: str = Field(default="whisper-large-v3", alias="GROQ_WHISPER_MODEL")
    groq_vision_model: str = Field(default="qwen/qwen3.8-27b", alias="GROQ_VISION_MODEL")
    groq_vision_timeout: float = Field(default=30.0, alias="GROQ_VISION_TIMEOUT")
    groq_vision_max_retries: int = Field(default=3, alias="GROQ_VISION_MAX_RETRIES")
    max_upload_size_bytes: int = Field(default=26214400, alias="MAX_UPLOAD_SIZE_BYTES")
    personal_health_log_level: str = Field(default="INFO", alias="PERSONAL_HEALTH_LOG_LEVEL")
    database_url: str = Field(default="sqlite:///./data/trustline_edge.db", alias="DATABASE_URL")

    base_dir: Path = Path(__file__).resolve().parent.parent
    ai_engine_dir: Path = Path(__file__).resolve().parent.parent.parent.parent
    project_root: Path = Path(__file__).resolve().parent.parent.parent.parent.parent
    ml_artifacts_dir: Path = Path(__file__).resolve().parent.parent.parent.parent / "ml" / "artifacts"
    sensor_quality_dir: Path = Path(__file__).resolve().parent.parent.parent.parent / "agents" / "sensor_quality"
    data_dir: Path = Path(__file__).resolve().parent.parent / "data"
    output_dir: Path = Path(__file__).resolve().parent.parent / "data" / "output"
    upload_dir: Path = Path(__file__).resolve().parent.parent / "data" / "uploads"
    processed_docs_dir: Path = Path(__file__).resolve().parent.parent / "data" / "processed_docs"
    rag_dir: Path = Path(__file__).resolve().parent.parent / "rag"

    stress_decision_threshold: float = 0.50
    ultra_short_hrv_window_seconds: float = 300.0

settings = PersonalHealthSettings()

def get_settings() -> PersonalHealthSettings:
    """Retrieve singleton settings instance."""
    return settings
