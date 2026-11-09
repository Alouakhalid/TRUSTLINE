"""FastAPI API package for Personal Health Agent."""
from .document_router import router as document_router
from .app import create_app, app

__all__ = ["document_router", "create_app", "app"]
