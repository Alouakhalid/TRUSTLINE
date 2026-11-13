"""
Pydantic schemas, enums, and structured exceptions for TRUSTLINE Hybrid AI Router.
"""
from enum import Enum
from typing import Dict, Any, Optional, List
import uuid
from datetime import datetime
from pydantic import BaseModel, Field

class ProviderType(str, Enum):
    """Supported inference provider types."""
    GROQ = "GROQ"
    OLLAMA = "OLLAMA"
    HUGGINGFACE = "HUGGINGFACE"
    DETERMINISTIC = "DETERMINISTIC"

class ProviderStatus(str, Enum):
    """Health status of an inference provider."""
    HEALTHY = "HEALTHY"
    DEGRADED = "DEGRADED"
    UNAVAILABLE = "UNAVAILABLE"

class TaskCategory(str, Enum):
    """Explicit taxonomy of TRUSTLINE LLM inference tasks."""
    GENERAL_EXPLANATION = "general_explanation"
    CONCISE_SUMMARIZATION = "concise_summarization"
    STRUCTURED_EXTRACTION = "structured_extraction"
    AGENT_REPORT_FORMATTING = "agent_report_formatting"
    MEDICAL_DOCUMENT_OCR = "medical_document_ocr"
    MEDICAL_RAG_SYNTHESIS = "medical_rag_synthesis"
    PERSONAL_HEALTH_SYNTHESIS = "personal_health_synthesis"
    RISK_ASSESSMENT_SYNTHESIS = "risk_assessment_synthesis"
    TOOL_CALLING = "tool_calling"
    VOICE_INTERPRETATION = "voice_interpretation"
    SENSOR_QUALITY_BRIEFING = "sensor_quality_briefing"
    SUPERVISOR_FINAL_REPORT = "supervisor_final_report"

class RoutingPolicy(str, Enum):
    """Routing policy tier for tasks."""
    CLOUD_ONLY = "CLOUD_ONLY"
    LOCAL_ELIGIBLE = "LOCAL_ELIGIBLE"
    DETERMINISTIC_OFFLINE = "DETERMINISTIC_OFFLINE"
    UNAVAILABLE = "UNAVAILABLE"

class CircuitState(str, Enum):
    """Circuit breaker states for cloud routing."""
    CLOSED = "CLOSED"
    OPEN = "OPEN"
    HALF_OPEN = "HALF_OPEN"

class ProviderRequest(BaseModel):
    """Standardized request structure dispatched to inference providers."""
    request_id: str = Field(default_factory=lambda: f"REQ-{uuid.uuid4().hex[:8].upper()}")
    task_category: TaskCategory = TaskCategory.GENERAL_EXPLANATION
    prompt: str
    system_prompt: Optional[str] = None
    temperature: float = Field(default=0.1, ge=0.0, le=1.0)
    max_tokens: int = Field(default=1024, ge=1, le=8192)
    format_json: bool = False
    timeout_seconds: Optional[float] = None
    metadata: Dict[str, Any] = Field(default_factory=dict)

class ProviderResponse(BaseModel):
    """Standardized response structure emitted by inference providers."""
    request_id: str
    provider: ProviderType
    model: str
    content: str
    structured_data: Optional[Dict[str, Any]] = None
    latency_ms: float = 0.0
    tokens_per_second: Optional[float] = None
    is_fallback: bool = False
    fallback_reason: Optional[str] = None
    success: bool = True
    error_message: Optional[str] = None
    metadata: Dict[str, Any] = Field(default_factory=dict)

class ProviderHealth(BaseModel):
    """Health check outcome for a provider."""
    provider: ProviderType
    status: ProviderStatus
    latency_ms: float = 0.0
    error: Optional[str] = None
    last_checked_iso: str = Field(default_factory=lambda: datetime.utcnow().isoformat())
    details: Dict[str, Any] = Field(default_factory=dict)

# Structured Exceptions
class HybridAIError(Exception):
    """Base exception for Hybrid AI Router."""
    pass

class ProviderUnavailableError(HybridAIError):
    """Raised when an inference provider is unreachable or offline."""
    pass

class ProviderTimeoutError(HybridAIError):
    """Raised when an inference request exceeds the configured deadline."""
    pass

class ProviderRateLimitError(HybridAIError):
    """Raised when cloud inference encounters HTTP 429 rate limits."""
    pass

class ProviderAuthenticationError(HybridAIError):
    """Raised when cloud inference fails due to invalid or expired credentials."""
    pass

class TaskNotEligibleError(HybridAIError):
    """Raised when a task cannot be routed to the requested provider tier."""
    pass

class CircuitBreakerOpenError(HybridAIError):
    """Raised when cloud dispatch is short-circuited due to open circuit breaker."""
    pass

class OutputValidationError(HybridAIError):
    """Raised when model response fails schema or safety constraints."""
    pass
