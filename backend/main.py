"""Canonical TRUSTLINE API entrypoint: ``uvicorn backend.main:app``."""
from backend.api.app import app

__all__ = ["app"]
