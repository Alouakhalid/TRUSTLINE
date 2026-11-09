"""Unified medical extraction coordinator dispatching to PDF, DOCX, and standalone image handlers."""
import hashlib
import io
from pathlib import Path
from typing import List, Dict, Optional, Any, Union

from .schemas import (
    DocumentType,
    ExtractionMethod,
    ValidationStatus,
    ExtractedMedicalRecord,
    PageProcessingMetadata,
    DocumentProcessingResult
)
from .image_processor import ImageProcessor, ImageValidationError
from .groq_vision_client import GroqVisionClient, GroqVisionAPIError
from .pdf_reader import PDFReader, PDFProcessingError
from .docx_reader import DOCXReader, DOCXProcessingError
from .validator import MedicalDocumentValidator

class UnsupportedDocumentTypeError(Exception):
    """Raised when file format or MIME type cannot be identified or is unsupported."""
    pass

class MedicalDocumentExtractor:
    """High-level document extractor routing to specialized parsers and Groq Vision OCR."""

    def __init__(self, vision_client: Optional[GroqVisionClient] = None):
        self.vision_client = vision_client or GroqVisionClient()
        self.pdf_reader = PDFReader(vision_client=self.vision_client)
        self.docx_reader = DOCXReader(vision_client=self.vision_client)

    @classmethod
    def detect_document_type(
        cls,
        data: bytes,
        filename_hint: Optional[str] = None
    ) -> DocumentType:
        """Identify document type using magic signature headers and file extension."""
        if data.startswith(b"%PDF"):
            return DocumentType.PDF
        if data.startswith(b"PK\x03\x04"):
            if filename_hint and filename_hint.lower().endswith(".docx"):
                return DocumentType.DOCX
            return DocumentType.DOCX
        if data.startswith(b"\x89PNG\r\n\x1a\n"):
            return DocumentType.IMAGE
        if data.startswith(b"\xff\xd8\xff"):
            return DocumentType.IMAGE
        if data.startswith(b"RIFF") and len(data) > 12 and data[8:12] == b"WEBP":
            return DocumentType.IMAGE

        if filename_hint:
            lower_name = filename_hint.lower()
            if lower_name.endswith(".pdf"):
                return DocumentType.PDF
            if lower_name.endswith(".docx"):
                return DocumentType.DOCX
            if any(lower_name.endswith(ext) for ext in (".png", ".jpg", ".jpeg", ".webp")):
                return DocumentType.IMAGE

        return DocumentType.UNKNOWN

    def extract_document(
        self,
        document_input: Union[bytes, str, Path],
        document_id: str,
        filename_hint: Optional[str] = None,
        force_ocr: bool = False
    ) -> DocumentProcessingResult:
        """Route document payload to appropriate reader and return validated extraction result."""
        if isinstance(document_input, (str, Path)):
            path = Path(document_input)
            if not path.exists():
                raise FileNotFoundError(f"Document file does not exist: {path}")
            raw_bytes = path.read_bytes()
            effective_filename = filename_hint or path.name
        elif isinstance(document_input, bytes):
            raw_bytes = document_input
            effective_filename = filename_hint or f"doc_{document_id}"
        else:
            raise ValueError("Invalid document input type; expected bytes, str, or Path.")

        doc_type = self.detect_document_type(raw_bytes, effective_filename)

        if doc_type == DocumentType.PDF:
            return self.pdf_reader.process_pdf(
                pdf_input=raw_bytes,
                document_id=document_id,
                force_ocr=force_ocr
            )

        if doc_type == DocumentType.DOCX:
            return self.docx_reader.process_docx(
                docx_input=raw_bytes,
                document_id=document_id,
                skip_ocr=False
            )

        if doc_type == DocumentType.IMAGE:
            return self._process_standalone_image(
                image_bytes=raw_bytes,
                document_id=document_id,
                filename=effective_filename
            )

        raise UnsupportedDocumentTypeError(
            f"Unsupported document format for '{effective_filename}'. "
            "Supported formats: PDF, DOCX, PNG, JPEG, WEBP."
        )

    def _process_standalone_image(
        self,
        image_bytes: bytes,
        document_id: str,
        filename: str
    ) -> DocumentProcessingResult:
        """Process standalone image upload directly through Groq Vision OCR."""
        doc_warnings: List[str] = []
        try:
            data_url = ImageProcessor.bytes_to_base64_data_url(image_bytes)
        except ImageValidationError as ive:
            file_hash = hashlib.sha256(image_bytes).hexdigest()
            meta = PageProcessingMetadata(
                document_id=document_id,
                page_number=1,
                extraction_method=ExtractionMethod.NO_EXTRACTABLE_CONTENT,
                native_text_available=False,
                images_detected=1,
                ocr_required=True,
                ocr_status="FAILED",
                extraction_warnings=[str(ive)]
            )
            return DocumentProcessingResult(
                document_id=document_id,
                filename=filename,
                document_type=DocumentType.IMAGE,
                file_hash_sha256=file_hash,
                file_size_bytes=len(image_bytes),
                total_pages_or_images=1,
                page_metadata=[meta],
                extracted_records=[],
                overall_status="FAILED",
                processing_warnings=[str(ive)]
            )

        try:
            ocr_records = self.vision_client.extract_from_image_url(
                image_data_url=data_url,
                document_id=document_id,
                source_type="standalone_image",
                source_page_number=1,
                source_location=f"Image {filename}"
            )
            ocr_status = "SUCCESS"
        except GroqVisionAPIError as gve:
            doc_warnings.append(str(gve))
            ocr_records = []
            ocr_status = "FAILED"

        validated = [MedicalDocumentValidator.validate_record(r) for r in ocr_records]
        final_records = MedicalDocumentValidator.detect_duplicates_and_conflicts(validated)

        meta = PageProcessingMetadata(
            document_id=document_id,
            page_number=1,
            extraction_method=ExtractionMethod.GROQ_VISION_OCR,
            native_text_available=False,
            images_detected=1,
            ocr_required=True,
            ocr_status=ocr_status,
            extraction_warnings=doc_warnings
        )

        file_hash = hashlib.sha256(image_bytes).hexdigest()

        return DocumentProcessingResult(
            document_id=document_id,
            filename=filename,
            document_type=DocumentType.IMAGE,
            file_hash_sha256=file_hash,
            file_size_bytes=len(image_bytes),
            total_pages_or_images=1,
            page_metadata=[meta],
            extracted_records=final_records,
            overall_status="COMPLETED" if ocr_status == "SUCCESS" else "FAILED",
            processing_warnings=doc_warnings
        )
