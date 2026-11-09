"""Service managing mission operational context and spaceflight telemetry."""
from typing import Optional, Dict, Any
from ..schemas.mission_context import MissionContext, MissionPhase

class MissionContextService:
    """Service providing spaceflight operational context for health analysis."""

    def __init__(self, initial_context: Optional[MissionContext] = None):
        if initial_context:
            self._current_context = initial_context
        else:
            self._current_context = MissionContext(
                mission_id="UNKNOWN_MISSION",
                is_context_supplied=False
            )

    def get_mission_context(self, session_id: Optional[str] = None) -> MissionContext:
        """Fetch active operational spaceflight context."""
        return self._current_context

    def update_context(self, updated_fields: Dict[str, Any]) -> MissionContext:
        """Update operational spaceflight parameters."""
        data = self._current_context.model_dump()
        data.update(updated_fields)
        self._current_context = MissionContext(**data)
        return self._current_context
