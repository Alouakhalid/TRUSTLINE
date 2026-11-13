"""
Backward compatible alias for AIRouter using HybridAIRouter.
"""
from typing import Dict, Any, Optional
from .router import HybridAIRouter
from .schemas import ProviderRequest, TaskCategory

class AIRouter:
    def __init__(self):
        self.router = HybridAIRouter()

    async def route_request(
        self,
        prompt: str,
        urgency: str = "medium",
        dsn_connected: bool = False,
        context: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        if not dsn_connected or urgency.lower() == "critical":
            self.router.mode = "LOCAL_ONLY"
        else:
            self.router.mode = "HYBRID"

        req = ProviderRequest(
            task_category=TaskCategory.GENERAL_EXPLANATION,
            prompt=prompt,
            metadata=context or {}
        )
        resp = self.router.route_request(req)
        return {
            "provider": resp.provider.value.lower(),
            "model": resp.model,
            "status": "success" if resp.success else "failed",
            "response": resp.content,
            "is_fallback": resp.is_fallback,
            "latency_ms": resp.latency_ms
        }
