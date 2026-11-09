"""Repository for astronaut health profiles and historical clinical events."""
import json
from datetime import datetime
from typing import Optional, List, Dict, Any
from sqlalchemy import Column, String, Float, Integer, DateTime, Text
from .base import Base, SessionFactory, init_db
from ..schemas.health_profile import AstronautHealthProfile, HealthEvent

class AstronautProfileModel(Base):
    """SQLAlchemy model for astronaut health profiles."""
    __tablename__ = "astronaut_health_profiles"

    astronaut_id = Column(String(64), primary_key=True, index=True)
    height_cm = Column(Float, nullable=False)
    weight_kg = Column(Float, nullable=False)
    age = Column(Integer, nullable=True)
    blood_type = Column(String(16), nullable=True)
    serialized_profile = Column(Text, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

class HealthEventModel(Base):
    """SQLAlchemy model for historical health events."""
    __tablename__ = "health_events"

    event_id = Column(String(64), primary_key=True, index=True)
    astronaut_id = Column(String(64), index=True, nullable=False)
    event_type = Column(String(64), nullable=False)
    severity = Column(String(32), default="nominal")
    description = Column(Text, nullable=False)
    serialized_event = Column(Text, nullable=False)
    event_time = Column(DateTime, nullable=False)
    ingestion_time = Column(DateTime, default=datetime.utcnow)

class HealthProfileRepository:
    """Repository handling profile storage and retrieval operations."""

    def __init__(self):
        init_db()

    def save_profile(self, profile: AstronautHealthProfile) -> AstronautHealthProfile:
        """Store or update an astronaut health profile."""
        session = SessionFactory()
        try:
            profile_json = profile.model_dump_json()
            existing = session.query(AstronautProfileModel).filter_by(astronaut_id=profile.astronaut_id).first()
            if existing:
                existing.height_cm = profile.basic_info.height_cm
                existing.weight_kg = profile.basic_info.weight_kg
                existing.age = profile.basic_info.age
                existing.blood_type = profile.basic_info.blood_type
                existing.serialized_profile = profile_json
                existing.updated_at = datetime.utcnow()
            else:
                record = AstronautProfileModel(
                    astronaut_id=profile.astronaut_id,
                    height_cm=profile.basic_info.height_cm,
                    weight_kg=profile.basic_info.weight_kg,
                    age=profile.basic_info.age,
                    blood_type=profile.basic_info.blood_type,
                    serialized_profile=profile_json,
                    created_at=datetime.utcnow(),
                    updated_at=datetime.utcnow()
                )
                session.add(record)
            session.commit()
            return profile
        finally:
            session.close()

    def get_profile(self, astronaut_id: str) -> Optional[AstronautHealthProfile]:
        """Retrieve an astronaut profile by identifier."""
        session = SessionFactory()
        try:
            record = session.query(AstronautProfileModel).filter_by(astronaut_id=astronaut_id).first()
            if not record:
                return None
            data = json.loads(record.serialized_profile)
            return AstronautHealthProfile(**data)
        finally:
            session.close()

    def record_event(self, event: HealthEvent) -> HealthEvent:
        """Record an immutable health event with temporal provenance."""
        session = SessionFactory()
        try:
            event_json = event.model_dump_json()
            record = HealthEventModel(
                event_id=event.event_id,
                astronaut_id=event.astronaut_id,
                event_type=event.event_type,
                severity=event.severity,
                description=event.description,
                serialized_event=event_json,
                event_time=event.event_time,
                ingestion_time=event.ingestion_time
            )
            session.add(record)
            session.commit()
            return event
        finally:
            session.close()

    def get_recent_events(self, astronaut_id: str, limit: int = 10) -> List[HealthEvent]:
        """Fetch chronologically recent health events for an astronaut."""
        session = SessionFactory()
        try:
            records = session.query(HealthEventModel).filter_by(astronaut_id=astronaut_id).order_by(HealthEventModel.event_time.desc()).limit(limit).all()
            return [HealthEvent(**json.loads(r.serialized_event)) for r in records]
        finally:
            session.close()
