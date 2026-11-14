"""Lazy import bootstrap for the existing ai-engine and data-engineering stacks.

The backend must not duplicate agent logic. This module only makes the existing
packages importable (their directories carry hyphens, so they are not importable
as top-level module names) and reports truthfully when a stack is unavailable.
"""
from __future__ import annotations

import importlib
import os
import sys
from pathlib import Path
from typing import Any

_REPO_ROOT = Path(__file__).resolve().parents[2]


def _ensure_paths() -> None:
    ai_engine = Path(os.getenv("TRUSTLINE_AI_ENGINE_DIR", _REPO_ROOT / "ai-engine"))
    agents_dir = ai_engine / "agents"
    for candidate in (str(agents_dir), str(ai_engine)):
        if candidate not in sys.path and ai_engine.exists():
            sys.path.insert(0, candidate)


def import_attribute(module_path: str, attribute: str) -> Any:
    """Import ``attribute`` from ``module_path`` using the repo-local stack paths.

    Raises ImportError truthfully (never silently falls back to a stub) when the
    ai-engine stack is not present in the deployment.
    """
    _ensure_paths()
    module = importlib.import_module(module_path)
    return getattr(module, attribute)


def data_engineering_path(module_file: str) -> Path:
    """Resolve a file inside data-engineering (env-overridable for deployments)."""
    de_root = Path(os.getenv("TRUSTLINE_DATA_ENGINEERING_DIR", _REPO_ROOT / "data-engineering"))
    return de_root / module_file
