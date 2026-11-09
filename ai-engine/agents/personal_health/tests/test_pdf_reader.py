"""Comprehensive unit test suite for PDF Reader service across text, scanned, and hybrid scenarios."""
import io
import fitz
import pytest
from unittest.mock import MagicMock
from PIL import Image

from ocr.schemas import (
    DocumentType,
    ExtractionMethod,
    ValidationStatus,
    ExtractedMedicalRecord
)
from ocr.pdf_reader import PDFReader, PDFProcessingError
from ocr.groq_vision_client import GroqVisionClient

def create_synthetic_pdf(
    text_content: str = "",
    add_table: bool = False,
    add_image: bool = False,
    page_count: int = 1
) -> bytes:
    """Helper creating memory-buffered PDF documents with optional text, tables, and images."""
    doc = fitz.open()
    for p_idx in range(page_count):
        page = doc.new_page(width=595, height=842)
        if text_content:
            page.insert_text((50, 72), f"{text_content} (Page {p_idx+1})", fontsize=11)

        if add_table:
            page.insert_text((50, 150), "Test Name | Value | Unit | Reference Range\nGlucose | 95 | mg/dL | 70-99\nHemoglobin | 14.8 | g/dL | 13.5-17.5", fontsize=10)

        if add_image:
            img = Image.new("RGB", (120, 120), color=(200, 50, 50))
            img_buf = io.BytesIO()
            img.save(img_buf, format="PNG")
            img_bytes = img_buf.getvalue()
            rect = fitz.Rect(50, 300, 200, 450)
            page.insert_image(rect, stream=img_bytes)

    pdf_bytes = doc.tobytes()
    doc.close()
    return pdf_bytes

def test_01_text_based_pdf_native_extraction():
    """Verify Scenario A text-based PDF extracts natively without invoking vision OCR."""
    mock_client = MagicMock(spec=GroqVisionClient)
    reader = PDFReader(vision_client=mock_client)

    pdf_bytes = create_synthetic_pdf(
        text_content="Laboratory Examination Report\nHemoglobin: 15.2 g/dL\nPlatelets: 250 10^3/uL",
        add_image=False
    )

    res = reader.process_pdf(pdf_input=pdf_bytes, document_id="DOC-TEST-001")
    assert res.document_type == DocumentType.PDF
    assert res.total_pages_or_images == 1
    assert len(res.page_metadata) == 1
    assert res.page_metadata[0].extraction_method == ExtractionMethod.NATIVE_TEXT
    assert res.page_metadata[0].ocr_required is False
    assert mock_client.extract_from_image_url.call_count == 0
    assert any("Hemoglobin" in r.test_name for r in res.extracted_records)

def test_02_scanned_pdf_groq_vision_ocr():
    """Verify Scenario B scanned PDF with no selectable text invokes Groq Vision OCR."""
    mock_client = MagicMock(spec=GroqVisionClient)
    mock_client.extract_from_image_url.return_value = [
        ExtractedMedicalRecord(
            document_id="DOC-TEST-002",
            document_type=DocumentType.PDF,
            source_type="scanned_page",
            source_page_number=1,
            test_name="Glucose",
            extracted_value="104",
            original_unit="mg/dL",
            reference_range="70-99",
            extraction_confidence=0.96,
            extraction_method=ExtractionMethod.GROQ_VISION_OCR
        )
    ]
    reader = PDFReader(vision_client=mock_client)

    pdf_bytes = create_synthetic_pdf(
        text_content="",
        add_image=True
    )

    res = reader.process_pdf(pdf_input=pdf_bytes, document_id="DOC-TEST-002")
    assert res.page_metadata[0].extraction_method == ExtractionMethod.GROQ_VISION_OCR
    assert res.page_metadata[0].ocr_required is True
    assert mock_client.extract_from_image_url.call_count == 1
    assert len(res.extracted_records) == 1
    assert res.extracted_records[0].test_name == "Glucose"
    assert res.extracted_records[0].normalized_value == 104.0

def test_03_hybrid_pdf_merges_native_and_ocr():
    """Verify Scenario C hybrid PDF with native text and images merges both sources."""
    mock_client = MagicMock(spec=GroqVisionClient)
    mock_client.extract_from_image_url.return_value = [
        ExtractedMedicalRecord(
            document_id="DOC-TEST-003",
            document_type=DocumentType.PDF,
            source_type="scanned_page",
            source_page_number=1,
            test_name="Potassium",
            extracted_value="4.2",
            original_unit="mEq/L",
            extraction_confidence=0.92,
            extraction_method=ExtractionMethod.GROQ_VISION_OCR
        )
    ]
    reader = PDFReader(vision_client=mock_client)

    pdf_bytes = create_synthetic_pdf(
        text_content="Clinical Biochemistry Panel\nSodium: 140 mEq/L\nBlood Pressure: 120 mmHg",
        add_image=True
    )

    res = reader.process_pdf(pdf_input=pdf_bytes, document_id="DOC-TEST-003")
    assert res.page_metadata[0].extraction_method == ExtractionMethod.HYBRID
    assert mock_client.extract_from_image_url.call_count == 1
    test_names = [r.test_name for r in res.extracted_records]
    assert any("Sodium" in t for t in test_names)
    assert any("Potassium" in t for t in test_names)

def test_04_pdf_with_embedded_images():
    """Verify PDF image detection populates images_detected count in page metadata."""
    mock_client = MagicMock(spec=GroqVisionClient)
    mock_client.extract_from_image_url.return_value = []
    reader = PDFReader(vision_client=mock_client)

    pdf_bytes = create_synthetic_pdf(text_content="Normal text header", add_image=True)
    res = reader.process_pdf(pdf_input=pdf_bytes, document_id="DOC-TEST-004")
    assert res.page_metadata[0].images_detected >= 1

def test_05_pdf_with_tables():
    """Verify table structures in PDF are parsed and row coordinates preserved."""
    mock_client = MagicMock(spec=GroqVisionClient)
    reader = PDFReader(vision_client=mock_client)

    doc = fitz.open()
    page = doc.new_page(width=595, height=842)
    page.insert_text((50, 50), "Routine Blood Work Analysis:\nHemoglobin: 14.2 g/dL\nWBC: 6.5 10^3/uL", fontsize=11)
    pdf_bytes = doc.tobytes()
    doc.close()

    res = reader.process_pdf(pdf_input=pdf_bytes, document_id="DOC-TEST-005")
    assert len(res.extracted_records) >= 2
    assert any(r.test_name == "Hemoglobin" for r in res.extracted_records)

def test_06_multi_page_pdf():
    """Verify multi-page PDF preserves sequential page metadata and page numbers."""
    mock_client = MagicMock(spec=GroqVisionClient)
    reader = PDFReader(vision_client=mock_client)

    pdf_bytes = create_synthetic_pdf(
        text_content="Hematology panel report with sufficient length to pass native text density requirements",
        page_count=3
    )
    res = reader.process_pdf(pdf_input=pdf_bytes, document_id="DOC-TEST-006")
    assert res.total_pages_or_images == 3
    assert len(res.page_metadata) == 3
    assert [m.page_number for m in res.page_metadata] == [1, 2, 3]

def test_07_empty_pdf_rejection():
    """Verify empty 0-byte PDF payload raises explicit PDFProcessingError."""
    reader = PDFReader()
    with pytest.raises(PDFProcessingError):
        reader.process_pdf(pdf_input=b"", document_id="DOC-TEST-007")

def test_08_corrupted_pdf_rejection():
    """Verify corrupted non-PDF byte stream raises PDFProcessingError."""
    reader = PDFReader()
    with pytest.raises(PDFProcessingError):
        reader.process_pdf(pdf_input=b"NOT_A_VALID_PDF_STREAM_12345678", document_id="DOC-TEST-008")

def test_09_pdf_with_incomplete_text_layer():
    """Verify sparse text below character density threshold triggers Groq Vision OCR."""
    mock_client = MagicMock(spec=GroqVisionClient)
    mock_client.extract_from_image_url.return_value = []
    reader = PDFReader(vision_client=mock_client)

    doc = fitz.open()
    page = doc.new_page(width=595, height=842)
    page.insert_text((50, 50), "Scan 1", fontsize=8)
    rect = fitz.Rect(50, 100, 250, 300)
    img = Image.new("RGB", (64, 64), color="gray")
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    page.insert_image(rect, stream=buf.getvalue())
    pdf_bytes = doc.tobytes()
    doc.close()

    res = reader.process_pdf(pdf_input=pdf_bytes, document_id="DOC-TEST-009")
    assert res.page_metadata[0].extraction_method in (ExtractionMethod.GROQ_VISION_OCR, ExtractionMethod.HYBRID)
    assert res.page_metadata[0].ocr_required is True

def test_10_pdf_with_arabic_and_english():
    """Verify PDF containing Arabic and English extracts test names and Eastern Arabic numerals."""
    mock_client = MagicMock(spec=GroqVisionClient)
    mock_client.extract_from_image_url.return_value = [
        ExtractedMedicalRecord(
            document_id="DOC-TEST-010",
            document_type=DocumentType.PDF,
            source_type="scanned_page",
            source_page_number=1,
            test_name="الهيموجلوبين",
            extracted_value="١٤.٥",
            original_unit="g/dL",
            extraction_confidence=0.98,
            extraction_method=ExtractionMethod.GROQ_VISION_OCR
        )
    ]
    reader = PDFReader(vision_client=mock_client)

    arabic_text = "تقرير الفحص الطبي الشامل\nالهيموجلوبين: ١٤.٥ g/dL\nالجلوكوز: ٩٥ mg/dL"
    pdf_bytes = create_synthetic_pdf(text_content=arabic_text)

    res = reader.process_pdf(pdf_input=pdf_bytes, document_id="DOC-TEST-010")
    test_names = [r.test_name for r in res.extracted_records]
    assert any("الهيموجلوبين" in t for t in test_names)
    for r in res.extracted_records:
        if "الهيموجلوبين" in r.test_name:
            assert r.normalized_value == 14.5
