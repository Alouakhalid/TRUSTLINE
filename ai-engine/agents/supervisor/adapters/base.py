"""Base adapter interface for integrating TRUSTLINE specialized agents into Supervisor."""
import time
from abc import ABC, abstractmethod
from typing import Dict, Any, Tuple
from ..schemas.assessment import AgentExecutionState, AgentExecutionStatus

class BaseAgentAdapter(ABC):
    """Abstract base class for all agent adapters providing execution telemetry and error capture."""

    def __init__(self, agent_name: str):
        self.agent_name = agent_name

    @abstractmethod
    def run(self, state: Dict[str, Any]) -> Tuple[Dict[str, Any], AgentExecutionStatus]:
        """Execute agent task and return updated state slice along with execution status."""
        pass

    def execute_with_telemetry(self, state: Dict[str, Any]) -> Tuple[Dict[str, Any], AgentExecutionStatus]:
        """Wrap execution with execution timing and uniform exception isolation."""
        start_time = time.perf_counter()
        try:
            updates, status = self.run(state)
            elapsed_ms = (time.perf_counter() - start_time) * 1000.0
            status.execution_time_ms = round(elapsed_ms, 2)
            return updates, status
        except Exception as exc:
            elapsed_ms = (time.perf_counter() - start_time) * 1000.0
            status = AgentExecutionStatus(
                agent_name=self.agent_name,
                status=AgentExecutionState.FAILED,
                execution_time_ms=round(elapsed_ms, 2),
                error_message=str(exc),
                warnings=[f"{self.agent_name} raised uncaught exception: {str(exc)}"]
            )
            return {}, status
