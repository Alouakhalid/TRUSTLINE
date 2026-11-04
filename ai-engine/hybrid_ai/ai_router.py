"""
Hybrid AI Router for TRUSTLINE.
Dynamically decides whether to execute autonomous clinical inference locally
onboard the spacecraft or uplink via the Deep Space Network (DSN) to Earth ground station clusters,
balancing communication latency, blackout status, and urgency.
"""

from typing import Dict, Any, Optional
import os
import logging
from .cloud_provider import CloudAIProvider
from .local_provider import LocalAIProvider

logger = logging.getLogger(__name__)

class AIRouter:
    def __init__(self):
        self.mode = os.getenv("AI_ROUTER_MODE", "HYBRID").upper()
        self.local_provider = LocalAIProvider()
        self.cloud_provider = CloudAIProvider()

    async def route_request(
        self,
        prompt: str,
        urgency: str = "medium",
        dsn_connected: bool = False,
        context: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        Routes the diagnostic/telemetry request to the appropriate provider based on network link state and urgency.
        """
        logger.info(f"Routing request: mode={self.mode}, urgency={urgency}, dsn_connected={dsn_connected}")

        # If DSN is disconnected (blackout) or urgency is CRITICAL, immediately route to local edge
        if not dsn_connected or urgency.lower() == "critical" or self.mode == "LOCAL":
            logger.info("Engaging Local Edge AI provider for zero-latency response.")
            return await self.local_provider.generate_response(prompt, context)

        # If DSN uplink is established and routine complex analysis is requested, route to Cloud
        if self.mode == "CLOUD" or (self.mode == "HYBRID" and dsn_connected):
            try:
                return await self.cloud_provider.generate_response(prompt, context)
            except Exception as e:
                logger.warning(f"Cloud provider uplink failed: {e}. Falling back to Local Edge.")
                return await self.local_provider.generate_response(prompt, context)

        return await self.local_provider.generate_response(prompt, context)
