import os
import sys
import time
import json
from PIL import Image, ImageDraw, ImageFont
import numpy as np

# Ensure PYTHONPATH
sys.path.insert(0, os.path.abspath("ai-engine/agents"))
sys.path.insert(0, os.path.abspath("ai-engine"))

from personal_health.config.settings import get_settings
from ocr.groq_vision_client import GroqVisionClient
from ocr.image_processor import ImageProcessor
from ocr.validator import MedicalDocumentValidator

def run_test():
    settings = get_settings()
    api_key = os.environ.get("GROQ_API_KEY", "") or getattr(settings, "groq_api_key", None)
    if not api_key:
        print(json.dumps({"status": "NO_CREDENTIALS"}))
        return

    # Create synthetic, non-sensitive medical test image
    img = Image.new("RGB", (600, 200), color="white")
    draw = ImageDraw.Draw(img)
    draw.text((20, 20), "AEROSPACE MEDICAL LAB - PREFLIGHT", fill="black")
    draw.text((20, 60), "Astronaut ID: AST-001", fill="black")
    draw.text((20, 100), "Glucose: 98 mg/dL (Ref: 70-99)", fill="black")
    draw.text((20, 140), "Hemoglobin: 15.4 g/dL (Ref: 13.5-17.5)", fill="black")

    data_url = ImageProcessor.to_base64_data_url(img)

    client = GroqVisionClient(api_key=api_key, model="qwen/qwen3.8-27b", max_retries=1)
    
    t0 = time.time()
    try:
        records = client.extract_from_image_url(
            image_data_url=data_url,
            document_id="DOC-LIVE-VERIFY",
            source_type="synthetic_bitmap"
        )
        latency = round(time.time() - t0, 3)
        validated_records = [
            MedicalDocumentValidator.validate_record(r).model_dump()
            for r in records
        ]
        result = {
            "provider": "Groq Vision API",
            "model_id": "qwen/qwen3.8-27b",
            "http_status": 200,
            "status": "SUCCESS",
            "latency_seconds": latency,
            "real_image_submitted": True,
            "record_count": len(records),
            "records": [
                {
                    "test_name": r.test_name,
                    "extracted_value": r.extracted_value,
                    "original_unit": r.original_unit,
                    "reference_range": r.reference_range,
                    "confidence": r.extraction_confidence
                }
                for r in records
            ],
            "validation_outcomes": [
                {
                    "test_name": vr["test_name"],
                    "normalized_value": vr["normalized_value"],
                    "validation_status": vr["validation_status"]
                }
                for vr in validated_records
            ]
        }
        print(json.dumps(result, indent=2))
    except Exception as exc:
        latency = round(time.time() - t0, 3)
        exc_str = str(exc)
        status_code = 500
        if "429" in exc_str or "rate_limit" in exc_str.lower():
            status_code = 429
            status = "RATE_LIMITED"
        else:
            status = f"ERROR: {type(exc).__name__}"
        result = {
            "provider": "Groq Vision API",
            "model_id": "qwen/qwen3.8-27b",
            "http_status": status_code,
            "status": status,
            "latency_seconds": latency,
            "real_image_submitted": True,
            "error_detail": exc_str.split("\n")[0] if exc_str else ""
        }
        print(json.dumps(result, indent=2))

if __name__ == "__main__":
    run_test()
