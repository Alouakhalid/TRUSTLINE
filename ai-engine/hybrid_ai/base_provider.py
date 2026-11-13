"""
Abstract Base Provider interface for TRUSTLINE inference backends.
"""
from abc import ABC, abstractmethod
from typing import Optional
from .schemas import ProviderRequest, ProviderResponse, ProviderHealth, ProviderType

class BaseLLMProvider(ABC):
    """Abstract interface defining required provider methods."""

    def __init__(self, provider_type: ProviderType, default_model: str, default_timeout: float = 30.0):
        self.provider_type = provider_type
        self.default_model = default_model
        self.default_timeout = default_timeout

    @abstractmethod
    def health_check(self) -> ProviderHealth:
        """Execute a synchronous health check verifying connectivity."""
        pass

    @abstractmethod
    async def health_check_async(self) -> ProviderHealth:
        """Execute an asynchronous health check verifying connectivity."""
        pass

    @abstractmethod
    def generate(self, request: ProviderRequest) -> ProviderResponse:
        """Execute synchronous inference."""
        pass

    @abstractmethod
    async def generate_async(self, request: ProviderRequest) -> ProviderResponse:
        """Execute asynchronous inference."""
        pass
