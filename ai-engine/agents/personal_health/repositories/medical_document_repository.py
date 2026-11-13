"""SQLAlchemy models and repository for medical document tracking and pending review workflows."""
import json
from datetime import datetime
from typing import List, Optional, Dict, Any
from sqlalchemy import Column, String, Float, Integer, DateTime, Text, Boolean
from .base import Base, SessionFactory, init_db
from ..schemas.medical_document import (
    ReviewStatus,
    ExtractedMedicalRecord,
    ConfirmedMedicalFinding,
    ValidationStatus
)

class MedicalDocumentModel(Base):
    """SQLAlchemy model tracking uploaded medical document packages."""
    __tablename__ = "medical_documents"

    document_id = Column(String(64), primary_key=True, index=True)
    astronaut_id = Column(String(64), index=True, nullable=False)
    filename = Column(String(255), nullable=False)
    file_hash = Column(String(64), nullable=False, index=True)
    file_type = Column(String(32), nullable=False)
    file_size_bytes = Column(Integer, nullable=False)
    storage_path = Column(String(512), nullable=False)
    upload_timestamp = Column(DateTime, default=datetime.utcnow)
    processing_status = Column(String(32), default="UPLOADED")
    extraction_summary_json = Column(Text, default="{}")
    error_message = Column(Text, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

class PendingMedicalRecordModel(Base):
    """SQLAlchemy model for extracted medical values awaiting human-in-the-loop review."""
    __tablename__ = "pending_medical_records"

    record_id = Column(String(64), primary_key=True, index=True)
    document_id = Column(String(64), index=True, nullable=False)
    astronaut_id = Column(String(64), index=True, nullable=False)
    source_type = Column(String(32), default="page")
    source_page_number = Column(Integer, nullable=True)
    source_image_id = Column(String(64), nullable=True)
    source_location = Column(String(128), nullable=True)
    test_name = Column(String(128), nullable=False, index=True)
    extracted_value = Column(String(128), nullable=False)
    normalized_value = Column(Float, nullable=True)
    original_unit = Column(String(64), nullable=True)
    normalized_unit = Column(String(64), nullable=True)
    reference_range = Column(String(128), nullable=True)
    collection_date = Column(String(32), nullable=True)
    collection_time = Column(String(32), nullable=True)
    laboratory_name = Column(String(128), nullable=True)
    physician_name = Column(String(128), nullable=True)
    patient_identifier = Column(String(64), nullable=True)
    source_text = Column(Text, default="")
    extraction_confidence = Column(Float, default=1.0)
    validation_status = Column(String(32), default="NEEDS_REVIEW")
    validation_warnings_json = Column(Text, default="[]")
    extraction_method = Column(String(32), default="native_text")
    review_status = Column(String(32), default="PENDING_REVIEW", index=True)
    reviewed_by = Column(String(64), nullable=True)
    review_timestamp = Column(DateTime, nullable=True)
    review_notes = Column(Text, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    @property
    def conflict_detected(self) -> bool:
        return self.validation_status == "CONFLICTING_EXTRACTION" or "conflicting" in (self.validation_warnings_json or "").lower()

class MedicalDocumentRepository:
    """Repository managing document persistence, extraction results, and review decisions."""

    def __init__(self):
        init_db()

    def save_document(
        self,
        document_id: str,
        astronaut_id: str,
        filename: str,
        file_hash: str,
        file_type: str,
        file_size_bytes: int,
        storage_path: str,
        processing_status: str = "UPLOADED",
        extraction_summary: Optional[Dict[str, Any]] = None,
        error_message: Optional[str] = None
    ) -> MedicalDocumentModel:
        """Create or update a tracked medical document entry."""
        session = SessionFactory()
        try:
            summary_str = json.dumps(extraction_summary or {})
            existing = session.query(MedicalDocumentModel).filter_by(document_id=document_id).first()
            if existing:
                existing.processing_status = processing_status
                existing.extraction_summary_json = summary_str
                existing.error_message = error_message
                existing.updated_at = datetime.utcnow()
                session.commit()
                session.refresh(existing)
                session.expunge(existing)
                return existing

            record = MedicalDocumentModel(
                document_id=document_id,
                astronaut_id=astronaut_id,
                filename=filename,
                file_hash=file_hash,
                file_type=file_type,
                file_size_bytes=file_size_bytes,
                storage_path=storage_path,
                processing_status=processing_status,
                extraction_summary_json=summary_str,
                error_message=error_message,
                created_at=datetime.utcnow(),
                updated_at=datetime.utcnow()
            )
            session.add(record)
            session.commit()
            session.refresh(record)
            session.expunge(record)
            return record
        except Exception:
            session.rollback()
            raise
        finally:
            session.close()

    def get_document(self, document_id: str) -> Optional[MedicalDocumentModel]:
        """Fetch medical document record by identifier."""
        session = SessionFactory()
        try:
            rec = session.query(MedicalDocumentModel).filter_by(document_id=document_id).first()
            if rec:
                session.expunge(rec)
            return rec
        finally:
            session.close()

    def save_extracted_records(
        self,
        records: List[ExtractedMedicalRecord],
        astronaut_id: str
    ) -> List[PendingMedicalRecordModel]:
        """Persist extracted medical records in pending review quarantine."""
        session = SessionFactory()
        try:
            saved_models: List[PendingMedicalRecordModel] = []
            for r in records:
                existing = session.query(PendingMedicalRecordModel).filter_by(record_id=r.record_id).first()
                if existing:
                    existing.test_name = r.test_name
                    existing.extracted_value = r.extracted_value
                    existing.normalized_value = r.normalized_value
                    existing.original_unit = r.original_unit
                    existing.normalized_unit = r.normalized_unit
                    existing.reference_range = r.reference_range
                    existing.validation_status = r.validation_status.value
                    existing.validation_warnings_json = json.dumps(r.validation_warnings)
                    existing.updated_at = datetime.utcnow()
                    saved_models.append(existing)
                else:
                    item = PendingMedicalRecordModel(
                        record_id=r.record_id,
                        document_id=r.document_id,
                        astronaut_id=astronaut_id,
                        source_type=r.source_type,
                        source_page_number=r.source_page_number,
                        source_image_id=r.source_image_id,
                        source_location=r.source_location,
                        test_name=r.test_name,
                        extracted_value=r.extracted_value,
                        normalized_value=r.normalized_value,
                        original_unit=r.original_unit,
                        normalized_unit=r.normalized_unit,
                        reference_range=r.reference_range,
                        collection_date=r.collection_date,
                        collection_time=r.collection_time,
                        laboratory_name=r.laboratory_name,
                        physician_name=r.physician_name,
                        patient_identifier=r.patient_identifier_if_present,
                        source_text=r.source_text,
                        extraction_confidence=r.extraction_confidence,
                        validation_status=r.validation_status.value,
                        validation_warnings_json=json.dumps(r.validation_warnings),
                        extraction_method=r.extraction_method.value,
                        review_status=ReviewStatus.PENDING_REVIEW.value,
                        created_at=datetime.utcnow(),
                        updated_at=datetime.utcnow()
                    )
                    session.add(item)
                    saved_models.append(item)
            session.commit()
            for sm in saved_models:
                session.refresh(sm)
                session.expunge(sm)
            return saved_models
        except Exception:
            session.rollback()
            raise
        finally:
            session.close()

    def get_pending_records(self, astronaut_id: str) -> List[PendingMedicalRecordModel]:
        """Retrieve all medical records currently awaiting review for an astronaut."""
        session = SessionFactory()
        try:
            records = session.query(PendingMedicalRecordModel).filter_by(
                astronaut_id=astronaut_id,
                review_status=ReviewStatus.PENDING_REVIEW.value
            ).all()
            for r in records:
                session.expunge(r)
            return records
        finally:
            session.close()

    def get_records_by_document(self, document_id: str) -> List[PendingMedicalRecordModel]:
        """Retrieve all extracted records associated with a specific document."""
        session = SessionFactory()
        try:
            records = session.query(PendingMedicalRecordModel).filter_by(document_id=document_id).all()
            for r in records:
                session.expunge(r)
            return records
        finally:
            session.close()

    def get_record(self, record_id: str) -> Optional[PendingMedicalRecordModel]:
        """Fetch individual record by unique record identifier."""
        session = SessionFactory()
        try:
            rec = session.query(PendingMedicalRecordModel).filter_by(record_id=record_id).first()
            if rec:
                session.expunge(rec)
            return rec
        finally:
            session.close()

    def update_record_review(
        self,
        record_id: str,
        action: ReviewStatus,
        reviewer_id: str,
        review_notes: Optional[str] = None,
        edited_test_name: Optional[str] = None,
        edited_value: Optional[str] = None,
        edited_unit: Optional[str] = None,
        edited_reference_range: Optional[str] = None,
        edited_collection_date: Optional[str] = None
    ) -> Optional[PendingMedicalRecordModel]:
        """Apply clinical reviewer decision (confirm, edit, or reject) to a pending record."""
        session = SessionFactory()
        try:
            rec = session.query(PendingMedicalRecordModel).filter_by(record_id=record_id).first()
            if not rec:
                return None

            rec.review_status = action.value
            rec.reviewed_by = reviewer_id
            rec.review_timestamp = datetime.utcnow()
            rec.review_notes = review_notes

            if action == ReviewStatus.EDITED:
                if edited_test_name:
                    rec.test_name = edited_test_name
                if edited_value:
                    rec.extracted_value = edited_value
                    from ocr.validator import MedicalDocumentValidator
                    num_val, _ = MedicalDocumentValidator.parse_numeric_value(edited_value)
                    rec.normalized_value = num_val
                if edited_unit is not None:
                    rec.original_unit = edited_unit
                    rec.normalized_unit = edited_unit.strip().lower() if edited_unit else None
                if edited_reference_range is not None:
                    rec.reference_range = edited_reference_range
                if edited_collection_date is not None:
                    rec.collection_date = edited_collection_date
                rec.review_status = ReviewStatus.CONFIRMED.value

            session.commit()
            session.refresh(rec)
            session.expunge(rec)
            return rec
        except Exception:
            session.rollback()
            raise
        finally:
            session.close()

    def get_document_by_hash(self, file_hash: str, astronaut_id: Optional[str] = None) -> Optional[MedicalDocumentModel]:
        """Fetch existing medical document record by cryptographic SHA-256 hash."""
        session = SessionFactory()
        try:
            q = session.query(MedicalDocumentModel).filter_by(file_hash=file_hash)
            if astronaut_id:
                q = q.filter_by(astronaut_id=astronaut_id)
            rec = q.first()
            if rec:
                session.expunge(rec)
            return rec
        finally:
            session.close()

    def get_confirmed_records(self, astronaut_id: str) -> List[ConfirmedMedicalFinding]:
        """Query all confirmed clinical laboratory records for an astronaut."""
        session = SessionFactory()
        try:
            records = session.query(PendingMedicalRecordModel).filter_by(
                astronaut_id=astronaut_id,
                review_status=ReviewStatus.CONFIRMED.value
            ).all()

            findings: List[ConfirmedMedicalFinding] = []
            for r in records:
                finding = ConfirmedMedicalFinding(
                    record_id=r.record_id,
                    document_id=r.document_id,
                    astronaut_id=r.astronaut_id,
                    test_name=r.test_name,
                    value_string=r.extracted_value,
                    numeric_value=r.normalized_value,
                    unit=r.original_unit,
                    reference_range=r.reference_range,
                    collection_date=r.collection_date,
                    laboratory_name=r.laboratory_name,
                    confirmation_timestamp=r.review_timestamp or datetime.utcnow(),
                    confirmed_by=r.reviewed_by or "system",
                    is_historical=True,
                    source_type=r.source_type,
                    source_location=r.source_location,
                    extraction_method=r.extraction_method,
                    extraction_confidence=r.extraction_confidence,
                    original_text=r.source_text,
                    conflict_detected=(r.validation_status == "CONFLICTING_EXTRACTION")
                )
                findings.append(finding)
            return findings
        finally:
            session.close()
