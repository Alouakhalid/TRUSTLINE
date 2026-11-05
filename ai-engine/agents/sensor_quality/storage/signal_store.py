"""In-memory cache and metadata manager for biosignal streams."""
from typing import Dict, Optional, List
from ..schemas.signal_schema import SensorStreamData

class SignalStore:
    """Store for accessing loaded biosignals across quality analysis stages."""

    def __init__(self):
        self._streams: Dict[str, SensorStreamData] = {}
        self._session_id: Optional[str] = None
        self._astronaut_id: Optional[str] = None

    def initialize_session(self, astronaut_id: str, session_id: str):
        self._astronaut_id = astronaut_id
        self._session_id = session_id
        self._streams.clear()

    def store_stream(self, sensor_name: str, stream: SensorStreamData):
        self._streams[sensor_name.upper()] = stream

    def get_stream(self, sensor_name: str) -> Optional[SensorStreamData]:
        return self._streams.get(sensor_name.upper())

    def list_available_sensors(self) -> List[str]:
        return list(self._streams.keys())

    def clear(self):
        self._streams.clear()
        self._session_id = None
        self._astronaut_id = None
