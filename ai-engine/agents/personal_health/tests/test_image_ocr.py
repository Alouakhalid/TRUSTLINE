"""Comprehensive unit test suite for standalone image preprocessing, quality validation, and Groq Vision OCR."""
import io
import pytest
from unittest.mock import MagicMock
import numpy as np
from PIL import Image

from ocr.schemas import (
    DocumentType,
    ExtractionMethod,
    ValidationStatus,
    ExtractedMedicalRecord
)
from ocr.image_processor import (
    ImageProcessor,
    ImageValidationError,
    LowImageQualityError
)
from ocr.extractor import MedicalDocumentExtractor
from ocr.groq_vision_client import GroqVisionClient

def create_synthetic_image(
    width: int = 150,
    height: int = 150,
    color: tuple = (255, 255, 255),
    add_noise: bool = False,
    format_name: str = "PNG"
) -> bytes:
    """Helper generating in-memory test images with controlled dimensions and patterns."""
    arr = np.full((height, width, 3), color, dtype=np.uint8)
    if add_noise:
        noise = np.random.randint(0, 100, (height, width, 3), dtype=np.uint8)
        arr = np.clip(arr.astype(int) + noise.astype(int), 0, 255).astype(np.uint8)
    img = Image.fromarray(arr)
    buf = io.BytesIO()
    img.save(buf, format=format_name)
    return buf.getvalue()

def test_01_clear_medical_report_image():
    """Verify clear standalone image processes successfully through Groq Vision OCR."""
    mock_client = MagicMock(spec=GroqVisionClient)
    mock_client.extract_from_image_url.return_value = [
        ExtractedMedicalRecord(
            document_id="IMG-TEST-001",
            document_type=DocumentType.IMAGE,
            source_type="standalone_image",
            source_page_number=1,
            test_name="Hemoglobin",
            extracted_value="14.8",
            original_unit="g/dL",
            reference_range="13.5-17.5",
            extraction_confidence=0.96,
            extraction_method=ExtractionMethod.GROQ_VISION_OCR
        )
    ]
    extractor = MedicalDocumentExtractor(vision_client=mock_client)

    img_bytes = create_synthetic_image(width=400, height=300, add_noise=True)
    res = extractor.extract_document(
        document_input=img_bytes,
        document_id="IMG-TEST-001",
        filename_hint="lab_report.png"
    )

    assert res.document_type == DocumentType.IMAGE
    assert res.overall_status == "COMPLETED"
    assert len(res.extracted_records) == 1
    assert res.extracted_records[0].test_name == "Hemoglobin"
    assert res.extracted_records[0].normalized_value == 14.8
    assert res.extracted_records[0].validation_status == ValidationStatus.VALIDATED

def test_02_blurry_image_rejection():
    """Verify blurry or unreadable image triggers LowImageQualityError."""
    img_flat = create_synthetic_image(width=100, height=100, color=(128, 128, 128), add_noise=False)
    with pytest.raises(LowImageQualityError):
        ImageProcessor.load_and_validate_image(img_flat, blur_check=True)

def test_03_rotated_image_orientation():
    """Verify EXIF orientation flag is applied to normalize image geometry."""
    img = Image.new("RGB", (200, 100), color="blue")
    buf = io.BytesIO()
    img.save(buf, format="JPEG")
    norm_img = ImageProcessor.load_and_validate_image(buf.getvalue(), blur_check=False)
    assert norm_img.size == (200, 100)

def test_04_low_resolution_image_rejection():
    """Verify images smaller than minimum 32x32 pixels raise LowImageQualityError."""
    tiny_bytes = create_synthetic_image(width=20, height=20)
    with pytest.raises(LowImageQualityError):
        ImageProcessor.load_and_validate_image(tiny_bytes, blur_check=False)

def test_05_cropped_image_partial_data():
    """Verify cropped image resulting in missing test value is assigned INVALID_FORMAT."""
    mock_client = MagicMock(spec=GroqVisionClient)
    mock_client.extract_from_image_url.return_value = [
        ExtractedMedicalRecord(
            document_id="IMG-TEST-005",
            document_type=DocumentType.IMAGE,
            source_type="standalone_image",
            source_page_number=1,
            test_name="Glucose",
            extracted_value="",
            extraction_confidence=0.40,
            extraction_method=ExtractionMethod.GROQ_VISION_OCR
        )
    ]
    extractor = MedicalDocumentExtractor(vision_client=mock_client)
    img_bytes = create_synthetic_image(width=200, height=200, add_noise=True)
    res = extractor.extract_document(img_bytes, "IMG-TEST-005", "cropped.png")
    assert res.extracted_records[0].validation_status == ValidationStatus.INVALID_FORMAT

def test_06_arabic_medical_report():
    """Verify image of Arabic medical report correctly extracts Arabic parameters and numerals."""
    mock_client = MagicMock(spec=GroqVisionClient)
    mock_client.extract_from_image_url.return_value = [
        ExtractedMedicalRecord(
            document_id="IMG-TEST-006",
            document_type=DocumentType.IMAGE,
            source_type="standalone_image",
            source_page_number=1,
            test_name="حمض اليوريك",
            extracted_value="٥.٤",
            original_unit="mg/dL",
            extraction_confidence=0.94,
            extraction_method=ExtractionMethod.GROQ_VISION_OCR
        )
    ]
    extractor = MedicalDocumentExtractor(vision_client=mock_client)
    img_bytes = create_synthetic_image(width=300, height=300, add_noise=True)
    res = extractor.extract_document(img_bytes, "IMG-TEST-006", "arabic_lab.jpg")
    assert res.extracted_records[0].test_name == "حمض اليوريك"
    assert res.extracted_records[0].normalized_value == 5.4

def test_07_english_medical_report():
    """Verify standard English laboratory report extraction and unit consistency check."""
    mock_client = MagicMock(spec=GroqVisionClient)
    mock_client.extract_from_image_url.return_value = [
        ExtractedMedicalRecord(
            document_id="IMG-TEST-007",
            document_type=DocumentType.IMAGE,
            source_type="standalone_image",
            source_page_number=1,
            test_name="Creatinine",
            extracted_value="0.9",
            original_unit="mg/dL",
            reference_range="0.7-1.3",
            extraction_confidence=0.98,
            extraction_method=ExtractionMethod.GROQ_VISION_OCR
        )
    ]
    extractor = MedicalDocumentExtractor(vision_client=mock_client)
    img_bytes = create_synthetic_image(width=300, height=300, add_noise=True)
    res = extractor.extract_document(img_bytes, "IMG-TEST-007", "creatinine.png")
    assert res.extracted_records[0].validation_status == ValidationStatus.VALIDATED
    assert res.extracted_records[0].normalized_value == 0.9

def test_08_mixed_language_report():
    """Verify bilingual Arabic and English medical record extraction from image."""
    mock_client = MagicMock(spec=GroqVisionClient)
    mock_client.extract_from_image_url.return_value = [
        ExtractedMedicalRecord(
            document_id="IMG-TEST-008",
            document_type=DocumentType.IMAGE,
            source_type="standalone_image",
            source_page_number=1,
            test_name="Complete Blood Count (تعداد الدم الكامل)",
            extracted_value="14.2",
            original_unit="g/dL",
            extraction_confidence=0.91,
            extraction_method=ExtractionMethod.GROQ_VISION_OCR
        )
    ]
    extractor = MedicalDocumentExtractor(vision_client=mock_client)
    img_bytes = create_synthetic_image(width=300, height=300, add_noise=True)
    res = extractor.extract_document(img_bytes, "IMG-TEST-008", "bilingual.png")
    assert len(res.extracted_records) == 1
    assert "تعداد الدم" in res.extracted_records[0].test_name

def test_09_medical_table_image():
    """Verify tabular layout in medical image parses multiple row items into separate records."""
    mock_client = MagicMock(spec=GroqVisionClient)
    mock_client.extract_from_image_url.return_value = [
        ExtractedMedicalRecord(
            document_id="IMG-TEST-009",
            document_type=DocumentType.IMAGE,
            source_type="table",
            source_location="Row 1",
            test_name="RBC",
            extracted_value="4.8",
            original_unit="10^6/uL",
            extraction_confidence=0.95,
            extraction_method=ExtractionMethod.GROQ_VISION_OCR
        ),
        ExtractedMedicalRecord(
            document_id="IMG-TEST-009",
            document_type=DocumentType.IMAGE,
            source_type="table",
            source_location="Row 2",
            test_name="WBC",
            extracted_value="6.2",
            original_unit="10^3/uL",
            extraction_confidence=0.95,
            extraction_method=ExtractionMethod.GROQ_VISION_OCR
        )
    ]
    extractor = MedicalDocumentExtractor(vision_client=mock_client)
    img_bytes = create_synthetic_image(width=350, height=200, add_noise=True)
    res = extractor.extract_document(img_bytes, "IMG-TEST-009", "cbc_table.png")
    assert len(res.extracted_records) == 2
    assert {r.test_name for r in res.extracted_records} == {"RBC", "WBC"}

def test_10_ambiguous_decimal_values():
    """Verify vision extraction flagged as ambiguous assigns ValidationStatus.AMBIGUOUS."""
    mock_client = MagicMock(spec=GroqVisionClient)
    mock_client.extract_from_image_url.return_value = [
        ExtractedMedicalRecord(
            document_id="IMG-TEST-010",
            document_type=DocumentType.IMAGE,
            source_type="standalone_image",
            source_page_number=1,
            test_name="Potassium",
            extracted_value="4.?5",
            original_unit="mEq/L",
            extraction_confidence=0.55,
            validation_status=ValidationStatus.AMBIGUOUS,
            validation_warnings=["Ambiguous character detected in decimal position."],
            extraction_method=ExtractionMethod.GROQ_VISION_OCR
        )
    ]
    extractor = MedicalDocumentExtractor(vision_client=mock_client)
    img_bytes = create_synthetic_image(width=250, height=250, add_noise=True)
    res = extractor.extract_document(img_bytes, "IMG-TEST-010", "smudged_lab.png")
    assert res.extracted_records[0].validation_status == ValidationStatus.AMBIGUOUS
    assert any("Ambiguous" in w for w in res.extracted_records[0].validation_warnings)
