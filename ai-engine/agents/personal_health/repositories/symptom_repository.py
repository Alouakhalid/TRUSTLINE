"""Repository for persisting unified symptom events across modalities."""
import json
from datetime import datetime
from typing import Optional, List
from sqlalchemy import Column, String, DateTime, Text
from .base import Base, SessionFactory, init_db
from ..schemas.symptom_event import SymptomEvent

class SymptomRecordModel(Base):
    """SQLAlchemy model for recorded symptom events."""
    __tablename__ = "symptom_records"

    event_id = Column(String(64), primary_key=True, index=True)
    astronaut_id = Column(String(64), index=True, nullable=False)
    session_id = Column(String(64), index=True, nullable=False)
    symptom_type = Column(String(64), nullable=False)
    symptom_category = Column(String(64), nullable=False)
    severity = Column(String(32), nullable=True)
    input_channel = Column(String(32), nullable=False)
    serialized_event = Column(Text, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)

class SymptomRepository:
    """Repository managing symptom storage and querying."""

    def __init__(self):
        init_db()

    def save_symptom(self, symptom: SymptomEvent) -> SymptomEvent:
        """Persist a symptom event record."""
        session = SessionFactory()
        try:
            s_json = symptom.model_dump_json()
            record = SymptomRecordModel(
                event_id=symptom.event_id,
                astronaut_id=symptom.astronaut_id,
                session_id=symptom.session_id,
                symptom_type=symptom.symptom_type,
                symptom_category=symptom.symptom_category.value,
                severity=symptom.severity.value if symptom.severity else None,
                input_channel=symptom.input_channel.value,
                serialized_event=s_json,
                created_at=datetime.utcnow()
            )
            session.add(record)
            session.commit()
            return symptom
        finally:
            session.close()

    def get_session_symptoms(self, astronaut_id: str, session_id: str) -> List[SymptomEvent]:
        """Fetch all symptoms reported during a designated session."""
        session = SessionFactory()
        try:
            records = session.query(SymptomRecordModel).filter_by(
                astronaut_id=astronaut_id,
                session_id=session_id
            ).all()
            return [SymptomEvent(**json.loads(r.serialized_event)) for r in records]
        finally:
            session.close()
