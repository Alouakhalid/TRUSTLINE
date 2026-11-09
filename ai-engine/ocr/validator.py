"""Deterministic post-extraction validation layer for medical document intelligence."""
import re
from datetime import datetime
from typing import List, Dict, Optional, Tuple, Any

from .schemas import ExtractedMedicalRecord, ValidationStatus

class MedicalDocumentValidator:
    """Validates extracted medical values, units, ranges, and consistency independently of LLMs."""

    EASTERN_ARABIC_DIGITS: Dict[str, str] = {
        "٠": "0", "١": "1", "٢": "2", "٣": "3", "٤": "4",
        "٥": "5", "٦": "6", "٧": "7", "٨": "8", "٩": "9",
        "۰": "0", "۱": "1", "۲": "2", "۳": "3", "۴": "4",
        "۵": "5", "۶": "6", "۷": "7", "۸": "8", "۹": "9"
    }

    KNOWN_TEST_UNITS: Dict[str, List[str]] = {
        "hemoglobin": ["g/dl", "g/l", "mmol/l"],
        "wbc": ["10^3/ul", "/ul", "10^9/l", "k/ul", "cells/ul"],
        "rbc": ["10^6/ul", "/ul", "10^12/l", "m/ul"],
        "platelets": ["10^3/ul", "/ul", "10^9/l", "k/ul"],
        "glucose": ["mg/dl", "mmol/l"],
        "cholesterol": ["mg/dl", "mmol/l"],
        "triglycerides": ["mg/dl", "mmol/l"],
        "creatinine": ["mg/dl", "umol/l"],
        "potassium": ["meq/l", "mmol/l"],
        "sodium": ["meq/l", "mmol/l"],
        "heart_rate": ["bpm", "beats/min"],
        "blood_pressure": ["mmhg"],
        "temperature": ["c", "°c", "deg c"]
    }

    @classmethod
    def normalize_digits(cls, text: str) -> str:
        """Convert Eastern Arabic and Persian numerals to standard ASCII digits."""
        if not text:
            return ""
        chars = [cls.EASTERN_ARABIC_DIGITS.get(ch, ch) for ch in text]
        res = "".join(chars)
        res = res.replace("٫", ".")
        return res

    @classmethod
    def parse_numeric_value(cls, raw_val: str) -> Tuple[Optional[float], List[str]]:
        """Parse numeric values with support for decimals, inequalities, and international separators."""
        warnings: List[str] = []
        if not raw_val:
            return None, ["Empty or missing value string."]

        normalized = cls.normalize_digits(raw_val.strip())

        cleaned = re.sub(r"[^\d.,\-+eE<>]", "", normalized)

        match_ineq = re.match(r"^([<>]=?)\s*([+\-]?\d+(?:[.,]\d+)?(?:[eE][+\-]?\d+)?)$", cleaned)
        if match_ineq:
            num_part = match_ineq.group(2).replace(",", ".")
            try:
                val = float(num_part)
                warnings.append(f"Inequality value preserved as numeric boundary ({match_ineq.group(1)} {val}).")
                return val, warnings
            except ValueError:
                pass

        if "," in cleaned and "." in cleaned:
            if cleaned.rfind(",") > cleaned.rfind("."):
                cleaned = cleaned.replace(".", "").replace(",", ".")
            else:
                cleaned = cleaned.replace(",", "")
        elif "," in cleaned and "." not in cleaned:
            parts = cleaned.split(",")
            if len(parts) == 2 and len(parts[1]) in (1, 2, 3):
                cleaned = cleaned.replace(",", ".")
            else:
                cleaned = cleaned.replace(",", "")

        match_num = re.search(r"[-+]?\d+(?:\.\d+)?(?:[eE][-+]?\d+)?", cleaned)
        if not match_num:
            return None, [f"Could not parse numerical value from '{raw_val}'."]

        try:
            val = float(match_num.group(0))
            return val, warnings
        except ValueError:
            return None, [f"Numeric float conversion failed for string '{match_num.group(0)}'."]

    @classmethod
    def validate_record(cls, record: ExtractedMedicalRecord) -> ExtractedMedicalRecord:
        """Execute deterministic validation on an individual extracted medical record."""
        warnings: List[str] = list(record.validation_warnings)
        status: ValidationStatus = record.validation_status

        if not record.test_name or not record.test_name.strip():
            warnings.append("Missing medical test name.")
            record.validation_status = ValidationStatus.INVALID_FORMAT
            record.validation_warnings = warnings
            return record

        if not record.extracted_value or not record.extracted_value.strip():
            warnings.append("Missing extracted test value.")
            record.validation_status = ValidationStatus.INVALID_FORMAT
            record.validation_warnings = warnings
            return record

        parsed_val, num_warn = cls.parse_numeric_value(record.extracted_value)
        warnings.extend(num_warn)
        record.normalized_value = parsed_val

        if parsed_val is None:
            if status != ValidationStatus.AMBIGUOUS:
                status = ValidationStatus.NEEDS_REVIEW
                warnings.append("Non-numeric or qualitative medical test result.")
        else:
            if record.original_unit:
                unit_clean = record.original_unit.strip().lower()
                record.normalized_unit = unit_clean

                test_key = record.test_name.strip().lower()
                for known_k, valid_units in cls.KNOWN_TEST_UNITS.items():
                    if known_k in test_key:
                        if not any(vu in unit_clean for vu in valid_units):
                            warnings.append(
                                f"Unit '{record.original_unit}' is physiologically atypical for test '{record.test_name}'."
                            )
                            status = ValidationStatus.NEEDS_REVIEW
                        break
            else:
                warnings.append("Test extracted without an explicit measurement unit.")
                if status == ValidationStatus.VALIDATED:
                    status = ValidationStatus.NEEDS_REVIEW

            if record.collection_date:
                cls._validate_date(record.collection_date, warnings)

            if record.reference_range:
                cls._validate_reference_range(record.reference_range, warnings)

            if status not in (ValidationStatus.AMBIGUOUS, ValidationStatus.LOW_CONFIDENCE, ValidationStatus.INVALID_FORMAT):
                if record.extraction_confidence < 0.70:
                    status = ValidationStatus.LOW_CONFIDENCE
                elif not warnings:
                    status = ValidationStatus.VALIDATED
                else:
                    status = ValidationStatus.NEEDS_REVIEW

        record.validation_status = status
        record.validation_warnings = warnings
        return record

    @classmethod
    def _validate_date(cls, date_str: str, warnings: List[str]) -> None:
        """Validate format of extracted collection date."""
        normalized = cls.normalize_digits(date_str.strip())
        patterns = (
            "%Y-%m-%d", "%d/%m/%Y", "%m/%d/%Y",
            "%d-%m-%Y", "%Y/%m/%d", "%d.%m.%Y"
        )
        parsed = False
        for p in patterns:
            try:
                datetime.strptime(normalized, p)
                parsed = True
                break
            except ValueError:
                pass
        if not parsed:
            warnings.append(f"Unstandardized date format '{date_str}'.")

    @classmethod
    def _validate_reference_range(cls, range_str: str, warnings: List[str]) -> None:
        """Validate structure of extracted reference range."""
        normalized = cls.normalize_digits(range_str.strip())
        range_match = re.search(r"(\d+(?:\.\d+)?)\s*(?:-|to|–|—|إلى)\s*(\d+(?:\.\d+)?)", normalized)
        if range_match:
            try:
                low = float(range_match.group(1))
                high = float(range_match.group(2))
                if low > high:
                    warnings.append(f"Inverted reference range bounds ({low} > {high}).")
            except ValueError:
                pass
        elif not re.search(r"[<>]", normalized):
            warnings.append(f"Unparseable reference range expression '{range_str}'.")

    @classmethod
    def detect_duplicates_and_conflicts(
        cls,
        records: List[ExtractedMedicalRecord]
    ) -> List[ExtractedMedicalRecord]:
        """Audit list of records for duplicates and conflicting extractions."""
        lookup: Dict[str, List[ExtractedMedicalRecord]] = {}
        for r in records:
            key = r.test_name.strip().lower()
            lookup.setdefault(key, []).append(r)

        for test_key, group in lookup.items():
            if len(group) <= 1:
                continue

            unique_values = set(g.extracted_value.strip().lower() for g in group)
            if len(unique_values) == 1:
                for idx, r in enumerate(group):
                    if idx > 0:
                        r.validation_warnings.append(f"Duplicate extraction of test '{r.test_name}' on same document.")
            else:
                for r in group:
                    r.validation_status = ValidationStatus.CONFLICTING_EXTRACTION
                    r.validation_warnings.append(
                        f"Conflicting values detected for test '{r.test_name}' across extractions ({list(unique_values)})."
                    )

        return records
