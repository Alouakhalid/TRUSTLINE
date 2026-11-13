"""Safe baseline update manager enforcing anti-contamination guards and traceable versioning."""
import uuid
from datetime import datetime
from typing import Dict, List, Optional, Tuple, Any

from .schemas import (
    PersonalBaselineProfile,
    ObservationSession,
    BaselineUpdateLog,
    UpdateRejectionReason,
    BaselineReadinessState,
    PersonalDeviationReport
)
from .data_pipeline import BaselineDataPipeline
from .statistical_engine import RobustBaselineEngine
from .deviation_engine import PersonalDeviationEngine
from .repository import PersonalBaselineRepository

class SafeBaselineUpdateManager:
    """Manages baseline updates while strictly guarding against anomaly contamination and cross-astronaut leaks."""

    def __init__(
        self,
        repository: Optional[PersonalBaselineRepository] = None,
        data_pipeline: Optional[BaselineDataPipeline] = None,
        statistical_engine: Optional[RobustBaselineEngine] = None,
        deviation_engine: Optional[PersonalDeviationEngine] = None,
        max_composite_anomaly_for_update: float = 3.0
    ):
        self.repository = repository or PersonalBaselineRepository()
        self.data_pipeline = data_pipeline or BaselineDataPipeline()
        self.statistical_engine = statistical_engine or RobustBaselineEngine()
        self.deviation_engine = deviation_engine or PersonalDeviationEngine()
        self.max_composite_anomaly_for_update = max_composite_anomaly_for_update

    def evaluate_update_eligibility(
        self,
        session: ObservationSession,
        current_profile: Optional[PersonalBaselineProfile]
    ) -> Tuple[bool, Optional[UpdateRejectionReason], Optional[str]]:
        """Strictly verify whether a new session is safe to absorb into personal baseline."""
        target_astro = (session.astronaut_id or "").strip().upper()
        if not target_astro or target_astro in ("UNKNOWN", "AST-UNKNOWN"):
            return False, UpdateRejectionReason.UNKNOWN_IDENTITY, "Cannot update baseline for unknown astronaut identity."

        if current_profile:
            cur_astro = current_profile.astronaut_id.strip().upper()
            if target_astro != cur_astro:
                return (
                    False,
                    UpdateRejectionReason.CROSS_ASTRONAUT_VIOLATION,
                    f"Cross-astronaut violation: observation belongs to {target_astro}, but baseline belongs to {cur_astro}."
                )

        # Audit session data quality
        audit_res = self.data_pipeline.audit_and_filter_session(
            session=session,
            target_astronaut_id=target_astro
        )
        is_valid, reason, cleaned_feats = audit_res[0], audit_res[1], audit_res[2]

        if not is_valid:
            if "quality" in str(reason).lower() or "sensor" in str(reason).lower() or "sqa" in str(reason).lower():
                return False, UpdateRejectionReason.POOR_SENSOR_QUALITY, reason
            return False, UpdateRejectionReason.CORRUPTED_FEATURES, reason

        # Anomaly contamination check if baseline already established or provisional
        if current_profile and current_profile.readiness_state in (
            BaselineReadinessState.PROVISIONAL,
            BaselineReadinessState.ESTABLISHED
        ):
            dev_report = self.deviation_engine.evaluate_session(
                astronaut_id=target_astro,
                session_id=session.session_id,
                current_features=cleaned_feats,
                baseline_profile=current_profile,
                explicit_context=session.context_type
            )
            # Prevent learning from anomalous physiological spikes
            if dev_report.composite_deviation_score >= self.max_composite_anomaly_for_update:
                return (
                    False,
                    UpdateRejectionReason.ANOMALOUS_OBSERVATION,
                    f"Observation exhibits statistically unusual deviation (composite={dev_report.composite_deviation_score:.2f} >= {self.max_composite_anomaly_for_update}); update rejected to prevent baseline contamination."
                )
            if dev_report.unusual_signals_count >= 2:
                return (
                    False,
                    UpdateRejectionReason.ANOMALOUS_OBSERVATION,
                    f"Observation contains {dev_report.unusual_signals_count} anomalous signals; update rejected."
                )

        return True, None, None

    def update_baseline_with_session(
        self,
        session: ObservationSession,
        all_historical_sessions: List[ObservationSession],
        reason: str = "Standard longitudinal session assimilation"
    ) -> Tuple[bool, Optional[PersonalBaselineProfile], BaselineUpdateLog]:
        """Perform guarded baseline update, incrementing version and generating audit record."""
        target_astro = (session.astronaut_id or "").strip().upper()
        current_profile = self.repository.get_baseline(target_astro)
        from_version = current_profile.baseline_version if current_profile else 0

        is_eligible, rej_code, rej_message = self.evaluate_update_eligibility(
            session=session,
            current_profile=current_profile
        )

        log_id = f"LOG-{uuid.uuid4().hex[:12].upper()}"

        if not is_eligible:
            audit_log = BaselineUpdateLog(
                log_id=log_id,
                astronaut_id=target_astro,
                from_version=from_version,
                to_version=from_version,
                source_session_id=session.session_id,
                update_timestamp=datetime.utcnow(),
                update_reason=reason,
                is_successful=False,
                rejection_reason=rej_code
            )
            self.repository.record_audit_log(audit_log)
            return False, current_profile, audit_log

        # Include new session into historical collection and re-filter
        augmented_sessions = list(all_historical_sessions)
        if not any(s.session_id == session.session_id for s in augmented_sessions):
            augmented_sessions.append(session)

        valid_sessions, readiness_metrics = self.data_pipeline.prepare_dataset(
            raw_sessions=augmented_sessions,
            astronaut_id=target_astro
        )

        to_version = from_version + 1
        new_profile = self.statistical_engine.construct_personal_baseline(
            astronaut_id=target_astro,
            valid_sessions=valid_sessions,
            readiness_metrics=readiness_metrics,
            baseline_version=to_version
        )

        saved_profile = self.repository.save_baseline(new_profile, reason=reason)

        audit_log = BaselineUpdateLog(
            log_id=log_id,
            astronaut_id=target_astro,
            from_version=from_version,
            to_version=to_version,
            source_session_id=session.session_id,
            update_timestamp=datetime.utcnow(),
            update_reason=reason,
            is_successful=True,
            rejection_reason=None
        )
        self.repository.record_audit_log(audit_log)

        return True, saved_profile, audit_log

    def attempt_update(
        self,
        profile: Any,
        new_session: Any,
        deviation_report: Optional[PersonalDeviationReport] = None,
        sqa_score: float = 1.0,
        historical_sessions: Optional[List[ObservationSession]] = None
    ) -> Tuple[bool, Optional[PersonalBaselineProfile], Optional[str]]:
        """Convenience method for attempting an update on an existing profile."""
        if isinstance(profile, ObservationSession) and not isinstance(new_session, ObservationSession):
            actual_session = profile
            target_profile = self.repository.get_baseline(actual_session.astronaut_id)
        else:
            actual_session = new_session
            target_profile = profile

        if actual_session.sqa_overall_score is None:
            actual_session = actual_session.model_copy(update={"sqa_overall_score": sqa_score})
        history = list(historical_sessions or [])
        success, updated_profile, audit_log = self.update_baseline_with_session(
            session=actual_session,
            all_historical_sessions=history,
            reason="Incremental session update"
        )
        rej_str = audit_log.rejection_reason.value if audit_log.rejection_reason else None
        return success, updated_profile, rej_str

    def rollback(
        self,
        astronaut_id: str,
        target_version: int,
        reason: str = "Rollback",
        changed_by: str = "supervisor"
    ) -> Optional[PersonalBaselineProfile]:
        """Roll back an astronaut baseline to a previous snapshot."""
        return self.repository.rollback_to_version(
            astronaut_id=astronaut_id,
            target_version=target_version,
            reason=reason,
            changed_by=changed_by
        )
