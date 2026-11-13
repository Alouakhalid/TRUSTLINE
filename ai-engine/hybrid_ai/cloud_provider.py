"""
Backward compatible alias for CloudAIProvider using GroqProvider.
"""
from typing import Dict, Any, Optional
from .groq_provider import GroqProvider
from .schemas import ProviderRequest, TaskCategory

class CloudAIProvider:
    def __init__(self, api_key: Optional[str] = None, model: Optional[str] = None):
        self.provider = GroqProvider(api_key=api_key, model=model)

    async def generate_response(self, prompt: str, context: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        req = ProviderRequest(
            task_category=TaskCategory.GENERAL_EXPLANATION,
            prompt=prompt,
            metadata=context or {}
        )
        resp = self.provider.generate(req)
        return {
            "provider": "cloud",
            "model": resp.model,
            "status": "success",
            "response": resp.content,
            "context_preserved": bool(context)
        }
