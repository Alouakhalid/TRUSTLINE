"""Dedicated DOCX Reader service parsing native text, tables, and embedded medical images."""
import io
import os
import re
import hashlib
from pathlib import Path
from typing import List, Dict, Tuple, Optional, Any, Union
import docx

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
from .validator import MedicalDocumentValidator

class DOCXProcessingError(Exception):
    """Raised when DOCX document parsing encounters a fatal error."""
    pass

class DOCXReader:
    """DOCX ingestion service extracting paragraphs, structured tables, and embedded media."""

    def __init__(self, vision_client: Optional[GroqVisionClient] = None):
        self.vision_client = vision_client or GroqVisionClient()

    def process_docx(
        self,
        docx_input: Union[bytes, str, Path],
        document_id: str,
        skip_ocr: bool = False
    ) -> DocumentProcessingResult:
        """Process DOCX package extracting native text, tables, and embedded images."""
        if isinstance(docx_input, (str, Path)):
            path = Path(docx_input)
            if not path.exists():
                raise DOCXProcessingError(f"DOCX file does not exist: {path}")
            try:
                doc = docx.Document(str(path))
            except Exception as exc:
                raise DOCXProcessingError(f"Failed to load DOCX document: {str(exc)}") from exc
            file_bytes = path.read_bytes()
            filename = path.name
        elif isinstance(docx_input, bytes):
            if len(docx_input) == 0:
                raise DOCXProcessingError("Empty DOCX byte payload provided.")
            try:
                buf = io.BytesIO(docx_input)
                doc = docx.Document(buf)
            except Exception as exc:
                raise DOCXProcessingError(f"Failed to parse DOCX bytes: {str(exc)}") from exc
            file_bytes = docx_input
            filename = f"upload_{document_id}.docx"
        else:
            raise DOCXProcessingError("Unsupported DOCX input type.")

        all_records: List[ExtractedMedicalRecord] = []
        doc_warnings: List[str] = []

        table_records = self._extract_tables(doc, document_id)
        all_records.extend(table_records)

        paragraph_records = self._extract_paragraphs(doc, document_id)
        all_records.extend(paragraph_records)

        embedded_records, img_count = self._extract_embedded_images(
            doc=doc,
            document_id=document_id,
            skip_ocr=skip_ocr,
            doc_warnings=doc_warnings
        )
        all_records.extend(embedded_records)

        method = ExtractionMethod.NATIVE_TEXT
        if img_count > 0 and len(table_records) + len(paragraph_records) > 0:
            method = ExtractionMethod.HYBRID
        elif img_count > 0 and len(table_records) + len(paragraph_records) == 0:
            method = ExtractionMethod.GROQ_VISION_OCR
        elif len(all_records) == 0:
            method = ExtractionMethod.NO_EXTRACTABLE_CONTENT

        meta = PageProcessingMetadata(
            document_id=document_id,
            page_number=1,
            extraction_method=method,
            native_text_available=bool(table_records or paragraph_records),
            images_detected=img_count,
            ocr_required=bool(img_count > 0 and not skip_ocr),
            ocr_status="SUCCESS" if img_count > 0 else "NOT_REQUIRED",
            extraction_warnings=doc_warnings
        )

        validated_records = [MedicalDocumentValidator.validate_record(r) for r in all_records]
        final_records = MedicalDocumentValidator.detect_duplicates_and_conflicts(validated_records)

        file_hash = hashlib.sha256(file_bytes).hexdigest()

        return DocumentProcessingResult(
            document_id=document_id,
            filename=filename,
            document_type=DocumentType.DOCX,
            file_hash_sha256=file_hash,
            file_size_bytes=len(file_bytes),
            total_pages_or_images=1,
            page_metadata=[meta],
            extracted_records=final_records,
            overall_status="COMPLETED",
            processing_warnings=doc_warnings
        )

    def _extract_tables(
        self,
        doc: docx.Document,
        document_id: str
    ) -> List[ExtractedMedicalRecord]:
        """Extract medical tests and values from DOCX tables preserving coordinates."""
        records: List[ExtractedMedicalRecord] = []
        for tab_idx, table in enumerate(doc.tables, start=1):
            if not table.rows or len(table.rows) < 2:
                continue

            header_cells = [c.text.strip().lower() for c in table.rows[0].cells]
            test_col = -1
            val_col = -1
            unit_col = -1
            ref_col = -1

            for col_idx, col_name in enumerate(header_cells):
                if any(k in col_name for k in ("test", "parameter", "investigation", "analysis", "فحص", "تحليل")):
                    test_col = col_idx
                elif any(k in col_name for k in ("result", "value", "level", "نتيجة", "قيمة")):
                    val_col = col_idx
                elif any(k in col_name for k in ("unit", "وحدة")):
                    unit_col = col_idx
                elif any(k in col_name for k in ("reference", "normal", "range", "مرجع")):
                    ref_col = col_idx

            if test_col != -1 and val_col != -1:
                for row_idx, row in enumerate(table.rows[1:], start=1):
                    cells = row.cells
                    if len(cells) <= max(test_col, val_col):
                        continue
                    t_name = cells[test_col].text.strip()
                    v_str = cells[val_col].text.strip()
                    if not t_name or not v_str:
                        continue

                    u_str = cells[unit_col].text.strip() if unit_col != -1 and len(cells) > unit_col else None
                    r_str = cells[ref_col].text.strip() if ref_col != -1 and len(cells) > ref_col else None

                    rec = ExtractedMedicalRecord(
                        document_id=document_id,
                        document_type=DocumentType.DOCX,
                        source_type="table",
                        source_location=f"Table {tab_idx}, Row {row_idx}",
                        test_name=t_name,
                        extracted_value=v_str,
                        original_unit=u_str,
                        reference_range=r_str,
                        source_text=f"{t_name} | {v_str} | {u_str or ''} | {r_str or ''}",
                        extraction_confidence=1.0,
                        validation_status=ValidationStatus.NEEDS_REVIEW,
                        extraction_method=ExtractionMethod.NATIVE_TEXT
                    )
                    records.append(rec)
        return records

    def _extract_paragraphs(
        self,
        doc: docx.Document,
        document_id: str
    ) -> List[ExtractedMedicalRecord]:
        """Parse selectable paragraph text for key-value medical expressions."""
        records: List[ExtractedMedicalRecord] = []
        for p_idx, p in enumerate(doc.paragraphs, start=1):
            text = p.text.strip()
            if not text:
                continue

            match = re.search(
                r"^([A-Za-z\u0600-\u06FF\s\-_/]+)\s*[:=\t]\s*([<>]?\s*[-+]?\d+(?:[.,]\d+)?)\s*([A-Za-z/%°\u0600-\u06FF\^0-9]+)?",
                text
            )
            if match:
                t_name = match.group(1).strip()
                v_str = match.group(2).strip()
                u_str = match.group(3).strip() if match.group(3) else None

                rec = ExtractedMedicalRecord(
                    document_id=document_id,
                    document_type=DocumentType.DOCX,
                    source_type="paragraph",
                    source_location=f"Paragraph {p_idx}",
                    test_name=t_name,
                    extracted_value=v_str,
                    original_unit=u_str,
                    source_text=text,
                    extraction_confidence=0.98,
                    validation_status=ValidationStatus.NEEDS_REVIEW,
                    extraction_method=ExtractionMethod.NATIVE_TEXT
                )
                records.append(rec)
        return records

    def _extract_embedded_images(
        self,
        doc: docx.Document,
        document_id: str,
        skip_ocr: bool,
        doc_warnings: List[str]
    ) -> Tuple[List[ExtractedMedicalRecord], int]:
        """Extract embedded image parts from DOCX archive and invoke Groq Vision OCR."""
        records: List[ExtractedMedicalRecord] = []
        img_parts = [
            (rel_id, part)
            for rel_id, part in doc.part.related_parts.items()
            if "image" in part.content_type
        ]

        if not img_parts or skip_ocr:
            return records, len(img_parts)

        for img_idx, (rel_id, part) in enumerate(img_parts, start=1):
            img_bytes = part.blob
            img_id = f"IMG-{rel_id}-{img_idx}"
            try:
                data_url = ImageProcessor.bytes_to_base64_data_url(img_bytes, format_hint="PNG")
                ocr_recs = self.vision_client.extract_from_image_url(
                    image_data_url=data_url,
                    document_id=document_id,
                    source_type="embedded_image",
                    source_image_id=img_id,
                    source_location=f"Embedded Image {rel_id} ({part.partname})"
                )
                records.extend(ocr_recs)
            except ImageValidationError as ive:
                doc_warnings.append(f"Skipping embedded image {img_id}: {str(ive)}")
            except GroqVisionAPIError as gve:
                doc_warnings.append(f"Groq Vision OCR failed for embedded image {img_id}: {str(gve)}")
            except Exception as exc:
                doc_warnings.append(f"Unexpected error processing image {img_id}: {str(exc)}")

        return records, len(img_parts)
