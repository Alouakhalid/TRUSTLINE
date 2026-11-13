"""SQLAlchemy models and repository for persisting astronaut personal baselines, snapshots, and audit logs."""
import json
import uuid
from datetime import datetime
from typing import Dict, List, Optional, Any
from sqlalchemy import Column, String, Integer, Float, DateTime, Text, Boolean
from sqlalchemy.orm import Session

from ..repositories.base import Base, SessionFactory, init_db
from .schemas import (
    PersonalBaselineProfile,
    BaselineReadinessState,
    BaselineUpdateLog,
    UpdateRejectionReason
)

class AstronautBaselineModel(Base):
    """SQLAlchemy model storing the active personal baseline profile for an astronaut."""
    __tablename__ = "astronaut_personal_baselines"

    astronaut_id = Column(String(64), primary_key=True, index=True)
    baseline_version = Column(Integer, default=1, nullable=False)
    readiness_state = Column(String(32), default=BaselineReadinessState.INSUFFICIENT_DATA.value, nullable=False)
    total_calibrated_sessions = Column(Integer, default=0, nullable=False)
    total_valid_observations = Column(Integer, default=0, nullable=False)
    observation_period_days = Column(Float, default=0.0, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)
    last_observation_timestamp = Column(DateTime, nullable=True)
    serialized_profile = Column(Text, nullable=False)

class BaselineHistoryModel(Base):
    """Immutable versioned snapshot of historical baseline profiles for auditing and rollback."""
    __tablename__ = "astronaut_baseline_history"

    history_id = Column(String(64), primary_key=True, index=True)
    astronaut_id = Column(String(64), index=True, nullable=False)
    baseline_version = Column(Integer, nullable=False)
    readiness_state = Column(String(32), nullable=False)
    serialized_profile = Column(Text, nullable=False)
    change_reason = Column(String(255), nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)

class BaselineAuditLogModel(Base):
    """Audit trail tracking every baseline update attempt (both successful and rejected)."""
    __tablename__ = "astronaut_baseline_audit_logs"

    log_id = Column(String(64), primary_key=True, index=True)
    astronaut_id = Column(String(64), index=True, nullable=False)
    source_session_id = Column(String(64), nullable=False)
    from_version = Column(Integer, nullable=False)
    to_version = Column(Integer, nullable=False)
    is_successful = Column(Boolean, default=False, nullable=False)
    update_reason = Column(String(255), nullable=False)
    rejection_reason = Column(String(64), nullable=True)
    timestamp = Column(DateTime, default=datetime.utcnow, nullable=False)

class PersonalBaselineRepository:
    """Thread-safe persistence layer for astronaut personal baselines and versioned snapshots."""

    def __init__(self):
        init_db()

    def get_baseline(self, astronaut_id: str) -> Optional[PersonalBaselineProfile]:
        """Retrieve the active personal baseline profile for an astronaut."""
        if not astronaut_id or astronaut_id in ("UNKNOWN", "AST-UNKNOWN"):
            return None

        session: Session = SessionFactory()
        try:
            record = session.query(AstronautBaselineModel).filter_by(astronaut_id=astronaut_id).first()
            if not record:
                return None
            data = json.loads(record.serialized_profile)
            return PersonalBaselineProfile.model_validate(data)
        finally:
            session.close()

    def save_baseline(
        self,
        profile: PersonalBaselineProfile,
        reason: str = "Baseline update"
    ) -> PersonalBaselineProfile:
        """Save or update an astronaut baseline profile and create an immutable historical snapshot."""
        if not profile.astronaut_id or profile.astronaut_id in ("UNKNOWN", "AST-UNKNOWN"):
            raise ValueError(f"Cannot persist baseline for unverified astronaut identity: {profile.astronaut_id}")

        session: Session = SessionFactory()
        try:
            profile.updated_at = datetime.utcnow()
            serialized = profile.model_dump_json()

            existing = session.query(AstronautBaselineModel).filter_by(astronaut_id=profile.astronaut_id).first()
            if existing:
                existing.baseline_version = profile.baseline_version
                existing.readiness_state = profile.readiness_state.value
                existing.total_calibrated_sessions = profile.total_calibrated_sessions
                existing.total_valid_observations = profile.total_valid_observations
                existing.observation_period_days = profile.observation_period_days
                existing.last_observation_timestamp = profile.last_observation_timestamp
                existing.serialized_profile = serialized
                existing.updated_at = profile.updated_at
            else:
                record = AstronautBaselineModel(
                    astronaut_id=profile.astronaut_id,
                    baseline_version=profile.baseline_version,
                    readiness_state=profile.readiness_state.value,
                    total_calibrated_sessions=profile.total_calibrated_sessions,
                    total_valid_observations=profile.total_valid_observations,
                    observation_period_days=profile.observation_period_days,
                    created_at=profile.created_at,
                    updated_at=profile.updated_at,
                    last_observation_timestamp=profile.last_observation_timestamp,
                    serialized_profile=serialized
                )
                session.add(record)

            # Record immutable historical snapshot
            hist = BaselineHistoryModel(
                history_id=f"HIST-{uuid.uuid4().hex[:12].upper()}",
                astronaut_id=profile.astronaut_id,
                baseline_version=profile.baseline_version,
                readiness_state=profile.readiness_state.value,
                serialized_profile=serialized,
                change_reason=reason,
                created_at=profile.updated_at
            )
            session.add(hist)

            session.commit()
            return profile
        except Exception:
            session.rollback()
            raise
        finally:
            session.close()

    def rollback_to_version(
        self,
        astronaut_id: str,
        target_version: int,
        reason: str = "Rollback",
        changed_by: str = "supervisor"
    ) -> Optional[PersonalBaselineProfile]:
        """Roll back an astronaut baseline to a previously archived historical snapshot."""
        if not astronaut_id or astronaut_id in ("UNKNOWN", "AST-UNKNOWN"):
            return None

        session: Session = SessionFactory()
        try:
            snapshot = (
                session.query(BaselineHistoryModel)
                .filter_by(astronaut_id=astronaut_id, baseline_version=target_version)
                .order_by(BaselineHistoryModel.created_at.desc())
                .first()
            )
            if not snapshot:
                return None

            profile_data = json.loads(snapshot.serialized_profile)
            profile = PersonalBaselineProfile.model_validate(profile_data)
            existing = session.query(AstronautBaselineModel).filter_by(astronaut_id=astronaut_id).first()
            current_active_version = existing.baseline_version if existing else target_version
            profile.baseline_version = max(current_active_version + 1, target_version + 1)
            profile.updated_at = datetime.utcnow()
            profile.provenance_notes = f"Restored from historical snapshot version {target_version}."

            serialized = profile.model_dump_json()
            if existing:
                existing.baseline_version = profile.baseline_version
                existing.readiness_state = profile.readiness_state.value
                existing.total_calibrated_sessions = profile.total_calibrated_sessions
                existing.total_valid_observations = profile.total_valid_observations
                existing.observation_period_days = profile.observation_period_days
                existing.serialized_profile = serialized
                existing.updated_at = profile.updated_at

            # Add rollback snapshot
            hist = BaselineHistoryModel(
                history_id=f"HIST-{uuid.uuid4().hex[:12].upper()}",
                astronaut_id=astronaut_id,
                baseline_version=profile.baseline_version,
                readiness_state=profile.readiness_state.value,
                serialized_profile=serialized,
                change_reason=f"{reason} (Rollback to v{target_version} by {changed_by})",
                created_at=profile.updated_at
            )
            session.add(hist)
            session.commit()
            return profile
        except Exception:
            session.rollback()
            raise
        finally:
            session.close()

    def get_version_history(self, astronaut_id: str) -> List[Dict[str, Any]]:
        """List all historical version snapshots for an astronaut."""
        session: Session = SessionFactory()
        try:
            records = (
                session.query(BaselineHistoryModel)
                .filter_by(astronaut_id=astronaut_id)
                .order_by(BaselineHistoryModel.baseline_version.asc())
                .all()
            )
            return [
                {
                    "history_id": r.history_id,
                    "astronaut_id": r.astronaut_id,
                    "baseline_version": r.baseline_version,
                    "readiness_state": r.readiness_state,
                    "change_reason": r.change_reason,
                    "created_at": r.created_at.isoformat()
                }
                for r in records
            ]
        finally:
            session.close()

    def get_baseline_history(self, astronaut_id: str) -> List[Dict[str, Any]]:
        """Alias for get_version_history."""
        return self.get_version_history(astronaut_id)

    def record_audit_log(self, log: BaselineUpdateLog) -> None:
        """Persist an audit trail log entry."""
        session: Session = SessionFactory()
        try:
            entry = BaselineAuditLogModel(
                log_id=log.log_id,
                astronaut_id=log.astronaut_id,
                source_session_id=log.source_session_id,
                from_version=log.from_version,
                to_version=log.to_version,
                is_successful=log.is_successful,
                update_reason=log.update_reason,
                rejection_reason=log.rejection_reason.value if log.rejection_reason else None,
                timestamp=log.update_timestamp
            )
            session.add(entry)
            session.commit()
        except Exception:
            session.rollback()
        finally:
            session.close()

    def get_audit_logs(self, astronaut_id: str) -> List[BaselineUpdateLog]:
        """Retrieve audit history for an astronaut."""
        session: Session = SessionFactory()
        try:
            records = (
                session.query(BaselineAuditLogModel)
                .filter_by(astronaut_id=astronaut_id)
                .order_by(BaselineAuditLogModel.timestamp.desc())
                .all()
            )
            return [
                BaselineUpdateLog(
                    log_id=r.log_id,
                    astronaut_id=r.astronaut_id,
                    from_version=r.from_version,
                    to_version=r.to_version,
                    source_session_id=r.source_session_id,
                    update_timestamp=r.timestamp,
                    update_reason=r.update_reason,
                    is_successful=r.is_successful,
                    rejection_reason=UpdateRejectionReason(r.rejection_reason) if r.rejection_reason else None
                )
                for r in records
            ]
        finally:
            session.close()

    def delete_baseline(self, astronaut_id: str) -> bool:
        """Purge baseline profile and history for an astronaut (for testing / reset)."""
        session: Session = SessionFactory()
        try:
            session.query(AstronautBaselineModel).filter_by(astronaut_id=astronaut_id).delete()
            session.query(BaselineHistoryModel).filter_by(astronaut_id=astronaut_id).delete()
            session.query(BaselineAuditLogModel).filter_by(astronaut_id=astronaut_id).delete()
            session.commit()
            return True
        except Exception:
            session.rollback()
            return False
        finally:
            session.close()
