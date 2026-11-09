"""FastAPI application factory for TRUSTLINE Medical Document Intelligence."""
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from .document_router import router as document_router

def create_app() -> FastAPI:
    """Create and configure FastAPI instance with medical document endpoints."""
    app = FastAPI(
        title="TRUSTLINE Personal Health Agent — Document Intelligence API",
        description="Advanced medical document ingestion, Groq Vision OCR, and pending record review.",
        version="1.0.0"
    )

    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    app.include_router(document_router)

    @app.get("/health")
    async def health_check():
        return {"status": "HEALTHY", "service": "personal_health_document_intelligence"}

    return app

app = create_app()
