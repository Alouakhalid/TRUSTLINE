"""Service coordinating medical document uploads, security audits, extraction, and pending record creation."""
import hashlib
import io
import os
import uuid
import zipfile
from pathlib import Path
from typing import Optional, List, Dict, Any, Union

from ..config.settings import get_settings
from ..repositories.medical_document_repository import MedicalDocumentRepository
from ..schemas.medical_document import (
    DocumentUploadResponse,
    DocumentProcessResponse,
    DocumentType,
    ValidationStatus
)
from ocr.extractor import MedicalDocumentExtractor, UnsupportedDocumentTypeError
from ocr.schemas import DocumentProcessingResult

class DocumentSecurityError(Exception):
    """Raised when an uploaded document breaches size, archive ratio, or integrity limits."""
    pass

class DocumentIngestionService:
    """End-to-end medical document ingestion, security validation, and extraction orchestrator."""

    MAX_DOCX_UNCOMPRESSED_BYTES: int = 100 * 1024 * 1024
    MAX_DOCX_FILE_COUNT: int = 1000

    def __init__(
        self,
        repository: Optional[MedicalDocumentRepository] = None,
        extractor: Optional[MedicalDocumentExtractor] = None
    ):
        self.settings = get_settings()
        self.repository = repository or MedicalDocumentRepository()
        self.extractor = extractor or MedicalDocumentExtractor()
        self.upload_dir = self.settings.upload_dir
        self.upload_dir.mkdir(parents=True, exist_ok=True)

    def upload_document(
        self,
        file_bytes: bytes,
        filename: str,
        astronaut_id: str
    ) -> DocumentUploadResponse:
        """Validate, hash, and persist uploaded document package."""
        self._validate_file_security(file_bytes, filename)

        file_hash = hashlib.sha256(file_bytes).hexdigest()
        doc_id = f"DOC-{uuid.uuid4().hex[:8].upper()}"

        safe_name = "".join(c for c in filename if c.isalnum() or c in "._- ")
        storage_filename = f"{doc_id}_{safe_name}"
        storage_path = self.upload_dir / storage_filename
        storage_path.write_bytes(file_bytes)

        doc_type = MedicalDocumentExtractor.detect_document_type(file_bytes, filename)

        self.repository.save_document(
            document_id=doc_id,
            astronaut_id=astronaut_id,
            filename=filename,
            file_hash=file_hash,
            file_type=doc_type.value,
            file_size_bytes=len(file_bytes),
            storage_path=str(storage_path),
            processing_status="UPLOADED"
        )

        return DocumentUploadResponse(
            document_id=doc_id,
            astronaut_id=astronaut_id,
            filename=filename,
            file_hash_sha256=file_hash,
            file_type=doc_type,
            file_size_bytes=len(file_bytes),
            status="UPLOADED"
        )

    def process_document(
        self,
        document_id: str,
        force_ocr: bool = False
    ) -> DocumentProcessResponse:
        """Execute document intelligence extraction and save pending records."""
        doc_entry = self.repository.get_document(document_id)
        if not doc_entry:
            raise FileNotFoundError(f"Document record '{document_id}' not found.")

        storage_path = Path(doc_entry.storage_path)
        if not storage_path.exists():
            raise FileNotFoundError(f"Underlying document storage file missing: {storage_path}")

        raw_bytes = storage_path.read_bytes()

        try:
            result: DocumentProcessingResult = self.extractor.extract_document(
                document_input=raw_bytes,
                document_id=document_id,
                filename_hint=doc_entry.filename,
                force_ocr=force_ocr
            )

            self.repository.save_extracted_records(
                records=result.extracted_records,
                astronaut_id=doc_entry.astronaut_id
            )

            summary = {
                "overall_status": result.overall_status,
                "total_records": len(result.extracted_records),
                "warnings": result.processing_warnings
            }
            self.repository.save_document(
                document_id=document_id,
                astronaut_id=doc_entry.astronaut_id,
                filename=doc_entry.filename,
                file_hash=doc_entry.file_hash,
                file_type=doc_entry.file_type,
                file_size_bytes=doc_entry.file_size_bytes,
                storage_path=doc_entry.storage_path,
                processing_status=result.overall_status,
                extraction_summary=summary
            )

            validated_count = sum(1 for r in result.extracted_records if r.validation_status == ValidationStatus.VALIDATED)
            flagged_count = len(result.extracted_records) - validated_count

            return DocumentProcessResponse(
                document_id=document_id,
                astronaut_id=doc_entry.astronaut_id,
                filename=doc_entry.filename,
                document_type=result.document_type,
                overall_status=result.overall_status,
                total_pages_or_images=result.total_pages_or_images,
                total_extracted_records=len(result.extracted_records),
                pending_records_count=len(result.extracted_records),
                validated_records_count=validated_count,
                flagged_records_count=flagged_count,
                processing_warnings=result.processing_warnings
            )

        except Exception as exc:
            self.repository.save_document(
                document_id=document_id,
                astronaut_id=doc_entry.astronaut_id,
                filename=doc_entry.filename,
                file_hash=doc_entry.file_hash,
                file_type=doc_entry.file_type,
                file_size_bytes=doc_entry.file_size_bytes,
                storage_path=doc_entry.storage_path,
                processing_status="FAILED",
                error_message=str(exc)
            )
            raise

    def retry_document(self, document_id: str) -> DocumentProcessResponse:
        """Retry extraction on previously failed or incomplete document."""
        return self.process_document(document_id=document_id, force_ocr=True)

    def _validate_file_security(self, file_bytes: bytes, filename: str) -> None:
        """Audit upload payload against size limits and archive decompression bombs."""
        if len(file_bytes) == 0:
            raise DocumentSecurityError("Uploaded file is empty (0 bytes).")

        if len(file_bytes) > self.settings.max_upload_size_bytes:
            raise DocumentSecurityError(
                f"File size ({len(file_bytes)} bytes) exceeds maximum allowable limit of {self.settings.max_upload_size_bytes} bytes."
            )

        doc_type = MedicalDocumentExtractor.detect_document_type(file_bytes, filename)
        if doc_type == DocumentType.UNKNOWN:
            raise DocumentSecurityError(f"Rejected unverified document type for file '{filename}'.")

        if doc_type == DocumentType.DOCX:
            try:
                buf = io.BytesIO(file_bytes)
                with zipfile.ZipFile(buf, "r") as zf:
                    infos = zf.infolist()
                    if len(infos) > self.MAX_DOCX_FILE_COUNT:
                        raise DocumentSecurityError(
                            f"DOCX archive contains excessive entries ({len(infos)} > {self.MAX_DOCX_FILE_COUNT})."
                        )
                    total_uncompressed = sum(info.file_size for info in infos)
                    if total_uncompressed > self.MAX_DOCX_UNCOMPRESSED_BYTES:
                        raise DocumentSecurityError(
                            f"DOCX uncompressed payload exceeds safety threshold ({total_uncompressed} > {self.MAX_DOCX_UNCOMPRESSED_BYTES})."
                        )
            except zipfile.BadZipFile as bzf:
                raise DocumentSecurityError(f"Corrupted or invalid DOCX ZIP package: {str(bzf)}") from bzf
