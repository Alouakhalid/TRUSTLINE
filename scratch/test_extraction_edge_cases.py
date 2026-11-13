import sys
from pathlib import Path

root = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(root / "ai-engine"))
sys.path.insert(0, str(root / "ai-engine" / "agents"))

from ocr.validator import MedicalDocumentValidator
from ocr.schemas import ExtractedMedicalRecord, ValidationStatus, ExtractionMethod
from ocr.docx_reader import DOCXReader
import fitz
import docx

def test_edge_cases():
    print("=== STARTING MEDICAL EXTRACTION EDGE CASES AUDIT ===")

    # 1. Decimal values
    rec_decimal = ExtractedMedicalRecord(
        document_id="DOC-EDGE-01",
        test_name="Hemoglobin",
        extracted_value="14.8",
        original_unit="g/dL"
    )
    val_dec = MedicalDocumentValidator.validate_record(rec_decimal)
    print(f"1. Decimal extraction: Extracted='{val_dec.extracted_value}' -> Normalized={val_dec.normalized_value}, Unit={val_dec.normalized_unit}, Status={val_dec.validation_status}")
    assert val_dec.normalized_value == 14.8
    assert val_dec.normalized_unit == "g/dl"
    assert val_dec.validation_status in (ValidationStatus.VALIDATED, ValidationStatus.NEEDS_REVIEW)

    # 2. Inequality values (< 0.01, > 100, <= 5.0)
    rec_ineq1 = ExtractedMedicalRecord(
        document_id="DOC-EDGE-02",
        test_name="Troponin I",
        extracted_value="< 0.01",
        original_unit="ng/mL"
    )
    val_ineq1 = MedicalDocumentValidator.validate_record(rec_ineq1)
    print(f"2a. Inequality (< 0.01): Extracted='{val_ineq1.extracted_value}' -> Normalized={val_ineq1.normalized_value}, Status={val_ineq1.validation_status}")
    assert "< 0.01" in val_ineq1.extracted_value
    assert val_ineq1.normalized_value == 0.01

    rec_ineq2 = ExtractedMedicalRecord(
        document_id="DOC-EDGE-02",
        test_name="Platelets",
        extracted_value="> 450",
        original_unit="10^3/uL"
    )
    val_ineq2 = MedicalDocumentValidator.validate_record(rec_ineq2)
    print(f"2b. Inequality (> 450): Extracted='{val_ineq2.extracted_value}' -> Normalized={val_ineq2.normalized_value}")
    assert val_ineq2.normalized_value == 450.0

    # 3. Arabic numerals and Arabic text
    # In Arabic: ٩٥ is 95, ١٥.٢ is 15.2
    rec_arabic = ExtractedMedicalRecord(
        document_id="DOC-EDGE-03",
        test_name="سكر الدم",
        extracted_value="٩٥",
        original_unit="ملغ/ديسيلتر"
    )
    val_arabic = MedicalDocumentValidator.validate_record(rec_arabic)
    print(f"3. Arabic Numerals: Extracted='{val_arabic.extracted_value}' -> Normalized={val_arabic.normalized_value}")
    # Verify Arabic digit translation
    assert val_arabic.normalized_value == 95.0

    rec_arabic_dec = ExtractedMedicalRecord(
        document_id="DOC-EDGE-03",
        test_name="هيموجلوبين",
        extracted_value="١٤.٨",
        original_unit="غ/دل"
    )
    val_arabic_dec = MedicalDocumentValidator.validate_record(rec_arabic_dec)
    print(f"3b. Arabic Decimal: Extracted='{val_arabic_dec.extracted_value}' -> Normalized={val_arabic_dec.normalized_value}")
    assert val_arabic_dec.normalized_value == 14.8

    # 4. Missing units
    rec_no_unit = ExtractedMedicalRecord(
        document_id="DOC-EDGE-04",
        test_name="Potassium",
        extracted_value="4.2",
        original_unit=None
    )
    val_no_unit = MedicalDocumentValidator.validate_record(rec_no_unit)
    print(f"4. Missing Unit: Extracted='{val_no_unit.extracted_value}' -> Unit={val_no_unit.normalized_unit}, Warnings={val_no_unit.validation_warnings}")
    assert val_no_unit.normalized_value == 4.2
    assert any("unit" in w.lower() for w in val_no_unit.validation_warnings)
    assert val_no_unit.validation_status == ValidationStatus.NEEDS_REVIEW

    # 5. Missing dates
    rec_no_date = ExtractedMedicalRecord(
        document_id="DOC-EDGE-05",
        test_name="Sodium",
        extracted_value="142",
        original_unit="mmol/L",
        collection_date=None
    )
    val_no_date = MedicalDocumentValidator.validate_record(rec_no_date)
    print(f"5a. None Date: Status={val_no_date.validation_status}, Date={val_no_date.collection_date}")
    assert val_no_date.collection_date is None
    assert val_no_date.normalized_value == 142.0

    rec_bad_date = ExtractedMedicalRecord(
        document_id="DOC-EDGE-05",
        test_name="Sodium",
        extracted_value="142",
        original_unit="mmol/L",
        collection_date="unparseable_date_xyz"
    )
    val_bad_date = MedicalDocumentValidator.validate_record(rec_bad_date)
    print(f"5b. Malformed Date: Status={val_bad_date.validation_status}, Warnings={val_bad_date.validation_warnings}")
    assert any("date" in w.lower() for w in val_bad_date.validation_warnings)

    # 6. Ambiguous / Low confidence / unmapped parameters
    rec_ambig = ExtractedMedicalRecord(
        document_id="DOC-EDGE-06",
        test_name="Glucose (?)",
        extracted_value="9?",
        original_unit="mg/dL",
        validation_status=ValidationStatus.AMBIGUOUS,
        extraction_confidence=0.55
    )
    val_ambig = MedicalDocumentValidator.validate_record(rec_ambig)
    print(f"6a. Ambiguous extraction: Status={val_ambig.validation_status}, Confidence={val_ambig.extraction_confidence}")
    assert val_ambig.validation_status == ValidationStatus.AMBIGUOUS

    rec_low_conf = ExtractedMedicalRecord(
        document_id="DOC-EDGE-06",
        test_name="Hemoglobin",
        extracted_value="14.2",
        original_unit="g/dL",
        extraction_confidence=0.50
    )
    val_low_conf = MedicalDocumentValidator.validate_record(rec_low_conf)
    print(f"6b. Low Confidence: Status={val_low_conf.validation_status}, Confidence={val_low_conf.extraction_confidence}")
    assert val_low_conf.validation_status == ValidationStatus.LOW_CONFIDENCE

    # 7. Complex DOCX table parsing with coordinates
    doc = docx.Document()
    table = doc.add_table(rows=4, cols=4)
    headers = ["Investigation / Test", "Result", "Units", "Reference Range"]
    for c_idx, h in enumerate(headers):
        table.cell(0, c_idx).text = h
    rows = [
        ["Serum Glucose", "98.5", "mg/dL", "70.0 - 99.0"],
        ["Hemoglobin A1c", "5.4", "%", "4.0 - 5.6"],
        ["Total Bilirubin", "< 0.8", "mg/dL", "0.2 - 1.2"]
    ]
    for r_idx, row in enumerate(rows, start=1):
        for c_idx, val in enumerate(row):
            table.cell(r_idx, c_idx).text = val
    
    import io
    buf = io.BytesIO()
    doc.save(buf)
    docx_bytes = buf.getvalue()

    reader = DOCXReader()
    docx_res = reader.process_docx(docx_bytes, "DOC-TABLE-01", skip_ocr=True)
    print(f"7. Complex DOCX Table: Extracted {len(docx_res.extracted_records)} records")
    assert len(docx_res.extracted_records) == 3
    for r in docx_res.extracted_records:
        print(f"   - {r.test_name}: {r.extracted_value} {r.original_unit} ({r.source_location}, Ref: {r.reference_range})")
        assert "Table 1, Row" in r.source_location
        assert r.normalized_value is not None

    print("=== MEDICAL EXTRACTION EDGE CASES AUDIT: ALL CHECKS PASSED ===")

if __name__ == "__main__":
    test_edge_cases()
