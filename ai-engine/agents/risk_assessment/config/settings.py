"""Configuration settings for TRUSTLINE Risk Assessment Agent."""
import os
from pathlib import Path
from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict

def _find_env_file() -> str:
    """Locate active .env file across standard configuration paths."""
    candidates = (
        Path(__file__).resolve().parent.parent / ".env",
        Path(__file__).resolve().parent.parent.parent / "personal_health" / ".env",
        Path(__file__).resolve().parent.parent.parent / "sensor_quality" / ".env",
        Path(__file__).resolve().parent.parent.parent.parent.parent / ".env"
    )
    for c in candidates:
        if c.exists():
            return str(c)
    return str(Path(__file__).resolve().parent.parent / ".env")

class RiskAssessmentSettings(BaseSettings):
    """Pydantic settings managing environment, paths, and Groq LLM configurations."""
    model_config = SettingsConfigDict(
        env_file=_find_env_file(),
        env_file_encoding="utf-8",
        extra="ignore"
    )

    app_env: str = Field(default="development")
    groq_api_key: str = Field(default="", alias="GROQ_API_KEY")
    groq_model: str = Field(default="llama-3.3-70b-versatile", alias="GROQ_CHAT_MODEL")
    groq_timeout: float = Field(default=30.0, alias="GROQ_TIMEOUT")
    groq_max_retries: int = Field(default=3, alias="GROQ_MAX_RETRIES")
    temperature: float = Field(default=0.1)

    base_dir: Path = Path(__file__).resolve().parent.parent
    data_dir: Path = Path(__file__).resolve().parent.parent / "data"
    output_dir: Path = Path(__file__).resolve().parent.parent / "data" / "output"
    sensor_quality_dir: Path = Path(__file__).resolve().parent.parent.parent / "sensor_quality"
    personal_health_dir: Path = Path(__file__).resolve().parent.parent.parent / "personal_health"

_settings_instance = None

def get_risk_settings() -> RiskAssessmentSettings:
    """Singleton provider for risk assessment configuration settings."""
    global _settings_instance
    if _settings_instance is None:
        _settings_instance = RiskAssessmentSettings()
    return _settings_instance
