"""
Backward compatible alias for LocalAIProvider using OllamaProvider.
"""
from typing import Dict, Any, Optional
from .ollama_provider import OllamaProvider
from .schemas import ProviderRequest, TaskCategory

class LocalAIProvider:
    def __init__(self, endpoint: Optional[str] = None, model: Optional[str] = None):
        self.provider = OllamaProvider(base_url=endpoint, model=model)

    async def generate_response(self, prompt: str, context: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        req = ProviderRequest(
            task_category=TaskCategory.GENERAL_EXPLANATION,
            prompt=prompt,
            metadata=context or {}
        )
        resp = self.provider.generate(req)
        return {
            "provider": "local_edge",
            "model": resp.model,
            "status": "success",
            "response": resp.content,
            "latency_ms": resp.latency_ms,
            "offline_mode": True
        }
