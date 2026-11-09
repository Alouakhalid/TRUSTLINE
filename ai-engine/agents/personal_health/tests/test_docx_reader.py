"""Comprehensive unit test suite for DOCX Reader service across text, tables, and embedded media."""
import io
import pytest
from unittest.mock import MagicMock
import docx
from PIL import Image

from ocr.schemas import (
    DocumentType,
    ExtractionMethod,
    ValidationStatus,
    ExtractedMedicalRecord
)
from ocr.docx_reader import DOCXReader, DOCXProcessingError
from ocr.groq_vision_client import GroqVisionClient

def create_synthetic_docx(
    paragraphs: list = None,
    tables_data: list = None,
    image_count: int = 0
) -> bytes:
    """Helper building in-memory DOCX archives with paragraphs, tables, and embedded images."""
    doc = docx.Document()

    if paragraphs:
        for p_text in paragraphs:
            doc.add_paragraph(p_text)

    if tables_data:
        for tab in tables_data:
            if not tab:
                continue
            rows = len(tab)
            cols = len(tab[0])
            table = doc.add_table(rows=rows, cols=cols)
            for r_idx, row in enumerate(tab):
                for c_idx, val in enumerate(row):
                    table.cell(r_idx, c_idx).text = str(val)

    if image_count > 0:
        for i in range(image_count):
            img = Image.new("RGB", (80, 80), color=(50 + i * 40, 100, 150))
            buf = io.BytesIO()
            img.save(buf, format="PNG")
            buf.seek(0)
            doc.add_picture(buf)

    out_buf = io.BytesIO()
    doc.save(out_buf)
    return out_buf.getvalue()

def test_01_text_only_docx():
    """Verify DOCX with paragraphs and headings extracts native text without OCR."""
    mock_client = MagicMock(spec=GroqVisionClient)
    reader = DOCXReader(vision_client=mock_client)

    docx_bytes = create_synthetic_docx(
        paragraphs=[
            "Medical Briefing Report",
            "Hemoglobin: 15.4 g/dL",
            "Platelets: 280 10^3/uL"
        ]
    )

    res = reader.process_docx(docx_input=docx_bytes, document_id="DOC-DOCX-001")
    assert res.document_type == DocumentType.DOCX
    assert res.page_metadata[0].extraction_method == ExtractionMethod.NATIVE_TEXT
    assert res.page_metadata[0].ocr_required is False
    assert mock_client.extract_from_image_url.call_count == 0
    assert any(r.test_name == "Hemoglobin" for r in res.extracted_records)
    for r in res.extracted_records:
        if r.test_name == "Hemoglobin":
            assert r.normalized_value == 15.4

def test_02_docx_with_tables():
    """Verify DOCX with structured tables extracts cells and retains row/table coordinates."""
    mock_client = MagicMock(spec=GroqVisionClient)
    reader = DOCXReader(vision_client=mock_client)

    table_data = [
        ["Test Name", "Result", "Unit", "Reference Range"],
        ["Glucose", "92", "mg/dL", "70-99"],
        ["Cholesterol", "185", "mg/dL", "< 200"]
    ]
    docx_bytes = create_synthetic_docx(tables_data=[table_data])

    res = reader.process_docx(docx_input=docx_bytes, document_id="DOC-DOCX-002")
    assert len(res.extracted_records) == 2
    assert any(r.test_name == "Glucose" and r.source_type == "table" for r in res.extracted_records)
    for r in res.extracted_records:
        if r.test_name == "Glucose":
            assert r.normalized_value == 92.0
            assert "Table 1, Row 1" in r.source_location

def test_03_docx_with_embedded_image():
    """Verify embedded image inside DOCX is extracted from package and sent to Groq Vision."""
    mock_client = MagicMock(spec=GroqVisionClient)
    mock_client.extract_from_image_url.return_value = [
        ExtractedMedicalRecord(
            document_id="DOC-DOCX-003",
            document_type=DocumentType.DOCX,
            source_type="embedded_image",
            source_image_id="IMG-1",
            test_name="Potassium",
            extracted_value="4.1",
            original_unit="mEq/L",
            extraction_confidence=0.95,
            extraction_method=ExtractionMethod.GROQ_VISION_OCR
        )
    ]
    reader = DOCXReader(vision_client=mock_client)

    docx_bytes = create_synthetic_docx(
        paragraphs=["Lab report with attached image:"],
        image_count=1
    )

    res = reader.process_docx(docx_input=docx_bytes, document_id="DOC-DOCX-003")
    assert res.page_metadata[0].images_detected == 1
    assert res.page_metadata[0].ocr_required is True
    assert mock_client.extract_from_image_url.call_count == 1
    assert any(r.test_name == "Potassium" for r in res.extracted_records)

def test_04_docx_with_multiple_embedded_images():
    """Verify DOCX with multiple embedded images invokes Groq Vision for each distinct image."""
    mock_client = MagicMock(spec=GroqVisionClient)
    mock_client.extract_from_image_url.side_effect = [
        [
            ExtractedMedicalRecord(
                document_id="DOC-DOCX-004",
                document_type=DocumentType.DOCX,
                source_type="embedded_image",
                source_image_id="IMG-1",
                test_name="Sodium",
                extracted_value="139",
                original_unit="mEq/L",
                extraction_confidence=0.94,
                extraction_method=ExtractionMethod.GROQ_VISION_OCR
            )
        ],
        [
            ExtractedMedicalRecord(
                document_id="DOC-DOCX-004",
                document_type=DocumentType.DOCX,
                source_type="embedded_image",
                source_image_id="IMG-2",
                test_name="Calcium",
                extracted_value="9.5",
                original_unit="mg/dL",
                extraction_confidence=0.93,
                extraction_method=ExtractionMethod.GROQ_VISION_OCR
            )
        ]
    ]
    reader = DOCXReader(vision_client=mock_client)

    docx_bytes = create_synthetic_docx(image_count=2)
    res = reader.process_docx(docx_input=docx_bytes, document_id="DOC-DOCX-004")
    assert res.page_metadata[0].images_detected == 2
    assert mock_client.extract_from_image_url.call_count == 2
    test_names = [r.test_name for r in res.extracted_records]
    assert "Sodium" in test_names
    assert "Calcium" in test_names

def test_05_docx_with_arabic_text():
    """Verify DOCX containing Arabic paragraphs and Eastern Arabic numerals parses accurately."""
    mock_client = MagicMock(spec=GroqVisionClient)
    reader = DOCXReader(vision_client=mock_client)

    docx_bytes = create_synthetic_docx(
        paragraphs=[
            "تقرير الفحوصات المخبرية",
            "الهيموجلوبين: ١٥.٢ g/dL",
            "الجلوكوز: ٩٢ mg/dL"
        ]
    )

    res = reader.process_docx(docx_input=docx_bytes, document_id="DOC-DOCX-005")
    assert len(res.extracted_records) == 2
    test_names = [r.test_name for r in res.extracted_records]
    assert any("الهيموجلوبين" in t for t in test_names)
    for r in res.extracted_records:
        if "الهيموجلوبين" in r.test_name:
            assert r.normalized_value == 15.2

def test_06_docx_with_mixed_arabic_and_english():
    """Verify DOCX with mixed language content in both paragraphs and tables."""
    mock_client = MagicMock(spec=GroqVisionClient)
    reader = DOCXReader(vision_client=mock_client)

    table_data = [
        ["فحص (Test)", "قيمة (Value)", "وحدة (Unit)"],
        ["Hemoglobin (الهيموجلوبين)", "14.5", "g/dL"],
        ["Creatinine", "0.95", "mg/dL"]
    ]
    docx_bytes = create_synthetic_docx(
        paragraphs=["Summary / الملخص:", "Blood Pressure: 120 mmHg"],
        tables_data=[table_data]
    )

    res = reader.process_docx(docx_input=docx_bytes, document_id="DOC-DOCX-006")
    test_names = [r.test_name for r in res.extracted_records]
    assert any("Hemoglobin" in t or "الهيموجلوبين" in t for t in test_names)
    assert any("Blood Pressure" in t for t in test_names)

def test_07_docx_with_empty_paragraphs():
    """Verify DOCX with blank lines and whitespace paragraphs processes without failure."""
    mock_client = MagicMock(spec=GroqVisionClient)
    reader = DOCXReader(vision_client=mock_client)

    docx_bytes = create_synthetic_docx(
        paragraphs=["", "   ", "Hemoglobin: 14.1 g/dL", "", "   "]
    )

    res = reader.process_docx(docx_input=docx_bytes, document_id="DOC-DOCX-007")
    assert len(res.extracted_records) == 1
    assert res.extracted_records[0].test_name == "Hemoglobin"

def test_08_corrupted_docx_rejection():
    """Verify invalid or corrupted byte sequence raises DOCXProcessingError."""
    reader = DOCXReader()
    with pytest.raises(DOCXProcessingError):
        reader.process_docx(docx_input=b"MALFORMED_DOCX_NOT_A_ZIP", document_id="DOC-DOCX-008")

def test_09_docx_conflicting_text_and_image_values():
    """Verify conflicting values between native text and embedded image OCR are detected."""
    mock_client = MagicMock(spec=GroqVisionClient)
    mock_client.extract_from_image_url.return_value = [
        ExtractedMedicalRecord(
            document_id="DOC-DOCX-009",
            document_type=DocumentType.DOCX,
            source_type="embedded_image",
            source_image_id="IMG-1",
            test_name="Hemoglobin",
            extracted_value="12.0",
            original_unit="g/dL",
            extraction_confidence=0.95,
            extraction_method=ExtractionMethod.GROQ_VISION_OCR
        )
    ]
    reader = DOCXReader(vision_client=mock_client)

    docx_bytes = create_synthetic_docx(
        paragraphs=["Laboratory Summary:", "Hemoglobin: 15.0 g/dL"],
        image_count=1
    )

    res = reader.process_docx(docx_input=docx_bytes, document_id="DOC-DOCX-009")
    conflicts = [r for r in res.extracted_records if r.validation_status == ValidationStatus.CONFLICTING_EXTRACTION]
    assert len(conflicts) >= 2
    assert any("Conflicting values" in w for r in conflicts for w in r.validation_warnings)
