"""Dedicated PDF Reader service utilizing PyMuPDF for native text, table, and image processing."""
import io
import os
import re
from pathlib import Path
from typing import List, Dict, Tuple, Optional, Any, Union
import fitz

from .schemas import (
    DocumentType,
    ExtractionMethod,
    ValidationStatus,
    ExtractedMedicalRecord,
    PageProcessingMetadata,
    DocumentProcessingResult
)
from .image_processor import ImageProcessor
from .groq_vision_client import GroqVisionClient, GroqVisionAPIError
from .validator import MedicalDocumentValidator

class PDFProcessingError(Exception):
    """Raised when PDF reading or rendering encounters a fatal error."""
    pass

class PDFReader:
    """Multi-scenario PDF ingestion engine supporting text, scanned, and hybrid documents."""

    MIN_TEXT_CHARS_FOR_NATIVE: int = 40

    def __init__(self, vision_client: Optional[GroqVisionClient] = None):
        self.vision_client = vision_client or GroqVisionClient()

    def process_pdf(
        self,
        pdf_input: Union[bytes, str, Path],
        document_id: str,
        force_ocr: bool = False
    ) -> DocumentProcessingResult:
        """Process complete PDF document across all pages applying appropriate extraction strategy."""
        if isinstance(pdf_input, (str, Path)):
            path = Path(pdf_input)
            if not path.exists():
                raise PDFProcessingError(f"PDF file not found: {path}")
            try:
                doc = fitz.open(str(path))
            except Exception as exc:
                raise PDFProcessingError(f"Failed to open PDF document: {str(exc)}") from exc
            file_bytes = path.read_bytes()
            filename = path.name
        elif isinstance(pdf_input, bytes):
            if len(pdf_input) == 0:
                raise PDFProcessingError("Empty PDF payload supplied.")
            try:
                doc = fitz.open(stream=pdf_input, filetype="pdf")
            except Exception as exc:
                raise PDFProcessingError(f"Failed to parse PDF bytes: {str(exc)}") from exc
            file_bytes = pdf_input
            filename = f"upload_{document_id}.pdf"
        else:
            raise PDFProcessingError("Unsupported PDF input type.")

        try:
            total_pages = len(doc)
            if total_pages == 0:
                raise PDFProcessingError("PDF document contains 0 pages.")

            page_metas: List[PageProcessingMetadata] = []
            all_records: List[ExtractedMedicalRecord] = []
            doc_warnings: List[str] = []

            for page_idx in range(total_pages):
                page = doc[page_idx]
                page_num = page_idx + 1

                page_res, page_meta = self._process_page(
                    doc=doc,
                    page=page,
                    page_num=page_num,
                    document_id=document_id,
                    force_ocr=force_ocr
                )
                page_metas.append(page_meta)
                all_records.extend(page_res)
                doc_warnings.extend(page_meta.extraction_warnings)

            validated_records = [MedicalDocumentValidator.validate_record(r) for r in all_records]
            final_records = MedicalDocumentValidator.detect_duplicates_and_conflicts(validated_records)

            import hashlib
            file_hash = hashlib.sha256(file_bytes).hexdigest()

            has_failed_page = any(pm.ocr_status == "FAILED" for pm in page_metas)
            if has_failed_page:
                overall_status = "FAILED" if len(final_records) == 0 else "PARTIALLY_COMPLETED"
            else:
                overall_status = "COMPLETED"

            return DocumentProcessingResult(
                document_id=document_id,
                filename=filename,
                document_type=DocumentType.PDF,
                file_hash_sha256=file_hash,
                file_size_bytes=len(file_bytes),
                total_pages_or_images=total_pages,
                page_metadata=page_metas,
                extracted_records=final_records,
                overall_status=overall_status,
                processing_warnings=doc_warnings
            )
        finally:
            doc.close()

    def _process_page(
        self,
        doc: fitz.Document,
        page: fitz.Page,
        page_num: int,
        document_id: str,
        force_ocr: bool
    ) -> Tuple[List[ExtractedMedicalRecord], PageProcessingMetadata]:
        """Analyze individual PDF page and select native, scanned, or hybrid extraction strategy."""
        native_text = page.get_text("text").strip()
        images_info = page.get_images(full=True)
        img_count = len(images_info)

        corrupt_chars = native_text.count("·") + native_text.count("\ufffd") + native_text.count("\x00")
        is_incomplete_text_layer = bool(len(native_text) > 0 and (corrupt_chars / float(len(native_text)) > 0.15))

        has_sufficient_text = (
            len(native_text) >= self.MIN_TEXT_CHARS_FOR_NATIVE
            and not is_incomplete_text_layer
            and not force_ocr
        )

        records: List[ExtractedMedicalRecord] = []
        warnings: List[str] = []

        if is_incomplete_text_layer:
            warnings.append("Incomplete or malformed text layer detected; falling back to visual OCR.")

        if has_sufficient_text and img_count == 0:
            method = ExtractionMethod.NATIVE_TEXT
            records = self._extract_native_page(page, page_num, document_id)
            meta = PageProcessingMetadata(
                document_id=document_id,
                page_number=page_num,
                extraction_method=method,
                native_text_available=True,
                images_detected=0,
                ocr_required=False,
                ocr_status="NOT_REQUIRED"
            )
            return records, meta

        if not has_sufficient_text:
            method = ExtractionMethod.GROQ_VISION_OCR
            ocr_records, ocr_status, ocr_warn = self._ocr_rendered_page(page, page_num, document_id)
            records.extend(ocr_records)
            warnings.extend(ocr_warn)
            meta = PageProcessingMetadata(
                document_id=document_id,
                page_number=page_num,
                extraction_method=method,
                native_text_available=bool(native_text and not is_incomplete_text_layer),
                images_detected=img_count,
                ocr_required=True,
                ocr_status=ocr_status,
                extraction_warnings=warnings
            )
            return records, meta

        method = ExtractionMethod.HYBRID
        native_records = self._extract_native_page(page, page_num, document_id)
        records.extend(native_records)

        ocr_records, ocr_status, ocr_warn = self._ocr_rendered_page(page, page_num, document_id)
        records.extend(ocr_records)
        warnings.extend(ocr_warn)

        meta = PageProcessingMetadata(
            document_id=document_id,
            page_number=page_num,
            extraction_method=method,
            native_text_available=True,
            images_detected=img_count,
            ocr_required=True,
            ocr_status=ocr_status,
            extraction_warnings=warnings
        )
        return records, meta

    def _extract_native_page(
        self,
        page: fitz.Page,
        page_num: int,
        document_id: str
    ) -> List[ExtractedMedicalRecord]:
        """Parse selectable text and table structures directly from PDF page."""
        records: List[ExtractedMedicalRecord] = []

        try:
            tabs = page.find_tables()
            for tab_idx, tab in enumerate(tabs):
                df_rows = tab.extract()
                if not df_rows or len(df_rows) < 2:
                    continue
                header = [str(c or "").strip().lower() for c in df_rows[0]]

                test_col = -1
                val_col = -1
                unit_col = -1
                ref_col = -1

                for idx, col_name in enumerate(header):
                    if any(k in col_name for k in ("test", "parameter", "investigation", "analysis", "اسم الفحص", "التحليل")):
                        test_col = idx
                    elif any(k in col_name for k in ("result", "value", "level", "النتيجة", "القيمة")):
                        val_col = idx
                    elif any(k in col_name for k in ("unit", "الوحدة")):
                        unit_col = idx
                    elif any(k in col_name for k in ("reference", "normal", "range", "المعدل الطبيعي", "المرجع")):
                        ref_col = idx

                if test_col != -1 and val_col != -1:
                    for row_idx, row in enumerate(df_rows[1:], start=1):
                        if len(row) <= max(test_col, val_col):
                            continue
                        t_name = str(row[test_col] or "").strip()
                        v_str = str(row[val_col] or "").strip()
                        if not t_name or not v_str:
                            continue

                        u_str = str(row[unit_col] or "").strip() if unit_col != -1 and len(row) > unit_col else None
                        r_str = str(row[ref_col] or "").strip() if ref_col != -1 and len(row) > ref_col else None

                        rec = ExtractedMedicalRecord(
                            document_id=document_id,
                            document_type=DocumentType.PDF,
                            source_type="table",
                            source_page_number=page_num,
                            source_location=f"Page {page_num}, Table {tab_idx+1}, Row {row_idx}",
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
        except Exception:
            pass

        full_text = page.get_text("text")
        lines = [line.strip() for line in full_text.splitlines() if line.strip()]

        for line_idx, line in enumerate(lines):
            match = re.search(
                r"^([A-Za-z\u0600-\u06FF\s\-_/]+)\s*[:=\t]\s*([<>]?\s*[-+]?[\d\u0660-\u0669\u06F0-\u06F9]+(?:[.,٫][\d\u0660-\u0669\u06F0-\u06F9]+)?)\s*([A-Za-z/%°\u0600-\u06FF\^0-9]+)?",
                line
            )
            if match:
                t_name = match.group(1).strip()
                v_str = match.group(2).strip()
                u_str = match.group(3).strip() if match.group(3) else None

                if any(r.test_name.lower() == t_name.lower() for r in records):
                    continue

                rec = ExtractedMedicalRecord(
                    document_id=document_id,
                    document_type=DocumentType.PDF,
                    source_type="page_text",
                    source_page_number=page_num,
                    source_location=f"Page {page_num}, Line {line_idx+1}",
                    test_name=t_name,
                    extracted_value=v_str,
                    original_unit=u_str,
                    source_text=line,
                    extraction_confidence=0.98,
                    validation_status=ValidationStatus.NEEDS_REVIEW,
                    extraction_method=ExtractionMethod.NATIVE_TEXT
                )
                records.append(rec)

        return records

    def _ocr_rendered_page(
        self,
        page: fitz.Page,
        page_num: int,
        document_id: str
    ) -> Tuple[List[ExtractedMedicalRecord], str, List[str]]:
        """Render PDF page to image and invoke Groq Vision OCR."""
        warnings: List[str] = []
        try:
            pix = page.get_pixmap(dpi=200)
            img_bytes = pix.tobytes("png")
            data_url = ImageProcessor.bytes_to_base64_data_url(img_bytes, format_hint="PNG")

            ocr_results = self.vision_client.extract_from_image_url(
                image_data_url=data_url,
                document_id=document_id,
                source_type="scanned_page",
                source_page_number=page_num,
                source_location=f"Page {page_num} (Groq Vision OCR)"
            )
            return ocr_results, "SUCCESS", warnings
        except GroqVisionAPIError as gve:
            warnings.append(f"Groq Vision OCR failed for page {page_num}: {str(gve)}")
            return [], "FAILED", warnings
        except Exception as exc:
            warnings.append(f"Unexpected page rendering/OCR error on page {page_num}: {str(exc)}")
            return [], "FAILED", warnings
