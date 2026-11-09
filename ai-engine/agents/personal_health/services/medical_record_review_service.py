"""Service managing human-in-the-loop medical record review and health profile integration."""
import uuid
from datetime import datetime
from typing import List, Optional, Dict, Any

from ..repositories.medical_document_repository import (
    MedicalDocumentRepository,
    PendingMedicalRecordModel
)
from ..repositories.health_profile_repository import HealthProfileRepository
from ..services.health_profile_service import HealthProfileService
from ..schemas.medical_document import (
    ReviewStatus,
    RecordReviewRequest,
    RecordReviewResponse,
    ConfirmedMedicalFinding
)
from ..schemas.health_profile import HealthEvent

class RecordNotFoundError(Exception):
    """Raised when the target medical record cannot be located."""
    pass

class MedicalRecordReviewService:
    """Manages clinical review decisions and transitions confirmed records into astronaut health profile."""

    def __init__(
        self,
        document_repo: Optional[MedicalDocumentRepository] = None,
        health_profile_service: Optional[HealthProfileService] = None
    ):
        self.document_repo = document_repo or MedicalDocumentRepository()
        self.health_profile_service = health_profile_service or HealthProfileService()

    def get_pending_records(self, astronaut_id: str) -> List[Dict[str, Any]]:
        """Retrieve all extracted medical records pending review for an astronaut."""
        models = self.document_repo.get_pending_records(astronaut_id)
        results = []
        for m in models:
            results.append({
                "record_id": m.record_id,
                "document_id": m.document_id,
                "astronaut_id": m.astronaut_id,
                "test_name": m.test_name,
                "extracted_value": m.extracted_value,
                "normalized_value": m.normalized_value,
                "original_unit": m.original_unit,
                "reference_range": m.reference_range,
                "collection_date": m.collection_date,
                "source_type": m.source_type,
                "source_location": m.source_location,
                "extraction_confidence": m.extraction_confidence,
                "validation_status": m.validation_status,
                "review_status": m.review_status
            })
        return results

    def review_record(self, request: RecordReviewRequest) -> RecordReviewResponse:
        """Apply clinical reviewer decision and update astronaut health profile upon confirmation."""
        rec = self.document_repo.get_record(request.record_id)
        if not rec:
            raise RecordNotFoundError(f"Record with ID '{request.record_id}' does not exist.")

        updated = self.document_repo.update_record_review(
            record_id=request.record_id,
            action=request.action,
            reviewer_id=request.reviewer_id,
            review_notes=request.review_notes,
            edited_test_name=request.edited_test_name,
            edited_value=request.edited_value,
            edited_unit=request.edited_unit,
            edited_reference_range=request.edited_reference_range,
            edited_collection_date=request.edited_collection_date
        )

        assert updated is not None

        if request.action in (ReviewStatus.CONFIRMED, ReviewStatus.EDITED):
            self._integrate_confirmed_record(updated)

        msg = f"Record '{request.record_id}' review status updated to {updated.review_status}."
        return RecordReviewResponse(
            record_id=updated.record_id,
            document_id=updated.document_id,
            astronaut_id=updated.astronaut_id,
            review_status=ReviewStatus(updated.review_status),
            reviewed_by=updated.reviewed_by or request.reviewer_id,
            review_timestamp=updated.review_timestamp or datetime.utcnow(),
            message=msg
        )

    def _integrate_confirmed_record(self, record: PendingMedicalRecordModel) -> None:
        """Merge confirmed clinical finding into astronaut health profile and event log."""
        event = HealthEvent(
            event_id=f"EVT-{uuid.uuid4().hex[:8].upper()}",
            astronaut_id=record.astronaut_id,
            event_type="CLINICAL_LAB_MEASUREMENT",
            description=(
                f"Confirmed laboratory finding: {record.test_name} = {record.extracted_value} "
                f"{record.original_unit or ''} (Ref: {record.reference_range or 'N/A'}). "
                f"Source: Doc {record.document_id} ({record.source_location or 'N/A'})."
            ),
            severity="nominal",
            event_time=datetime.utcnow(),
            provenance_source=f"document_ocr:{record.document_id}",
            medical_officer_verdict=f"CONFIRMED_BY_{record.reviewed_by or 'REVIEWER'}"
        )
        self.health_profile_service.record_health_event(event)

        profile = self.health_profile_service.get_or_create_profile(record.astronaut_id)
        test_lower = record.test_name.lower()
        if "blood type" in test_lower or "blood group" in test_lower:
            profile.basic_info.blood_type = record.extracted_value.strip().upper()
            self.health_profile_service.save_profile(profile)

    def get_confirmed_findings(self, astronaut_id: str) -> List[ConfirmedMedicalFinding]:
        """Fetch all confirmed clinical findings available for astronaut health assessment."""
        return self.document_repo.get_confirmed_records(astronaut_id)
