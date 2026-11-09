"""TRUSTLINE Personal Health Agent package."""
import sys
from pathlib import Path

ai_engine_dir = Path(__file__).resolve().parent.parent.parent
if str(ai_engine_dir) not in sys.path:
    sys.path.insert(0, str(ai_engine_dir))

from .main import run_personal_health_pipeline

__all__ = ["run_personal_health_pipeline"]
