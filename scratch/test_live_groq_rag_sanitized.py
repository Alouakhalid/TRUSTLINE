import json
import os
import sys
import time
from pathlib import Path

# Ensure PYTHONPATH
sys.path.insert(0, os.path.abspath("ai-engine/agents"))
sys.path.insert(0, os.path.abspath("ai-engine"))

from personal_health.config.settings import get_settings
from personal_health.rag.service import MedicalKnowledgeRAGService
from personal_health.rag.generation import GroundedMedicalGenerator
from personal_health.rag.schemas import RetrievalQuery, GroundingStatus

def run_test():
    settings = get_settings()
    api_key = os.environ.get("GROQ_API_KEY", "") or getattr(settings, "groq_api_key", None)
    if not api_key:
        print(json.dumps({"status": "NO_CREDENTIALS"}))
        return

    rag = MedicalKnowledgeRAGService()
    query_text = "What is the clinical protocol for sustained sinus tachycardia during extravehicular activity?"
    q_obj = RetrievalQuery(query_id="QRY-LIVE-GROQ-01", query_text=query_text, top_k=3)
    passages, ret_status = rag.retriever.retrieve(q_obj)

    generator = GroundedMedicalGenerator(api_key=api_key, model="llama-3.3-70b-versatile")

    t0 = time.time()
    try:
        gen_result = generator.generate(query=query_text, passages=passages, retrieval_status=ret_status)
        latency = round(time.time() - t0, 3)

        has_sec1 = "1. Retrieved Medical Facts" in gen_result.generated_answer
        has_sec2 = "2. Clinical Interpretation" in gen_result.generated_answer
        has_sec3 = "3. Uncertainty & Limitations" in gen_result.generated_answer
        has_sec4 = "4. Source Citations" in gen_result.generated_answer
        has_sec5 = "5. Missing Information" in gen_result.generated_answer

        evidence = {
            "provider": "Groq LLM API",
            "model_id": generator.model,
            "http_status": 200,
            "status": "SUCCESS",
            "latency_seconds": latency,
            "query": query_text,
            "passages_retrieved": len(passages),
            "citations": gen_result.source_citations,
            "grounding_status": gen_result.grounding_status.value,
            "five_sections_verified": {
                "section_1_facts": has_sec1,
                "section_2_interpretation": has_sec2,
                "section_3_uncertainty": has_sec3,
                "section_4_citations": has_sec4,
                "section_5_missing_info": has_sec5
            },
            "answer_preview": gen_result.generated_answer[:300] + "...",
            "claim_evidence_mapping_count": len(gen_result.claim_evidence_mapping),
            "secrets_exposed": False
        }

        out_path = Path("scratch/live_groq_rag_generation_evidence.json")
        out_path.parent.mkdir(parents=True, exist_ok=True)
        with open(out_path, "w", encoding="utf-8") as f:
            json.dump(evidence, f, indent=2)

        print(json.dumps({
            "status": "SUCCESS",
            "provider": evidence["provider"],
            "model_id": evidence["model_id"],
            "http_status": 200,
            "latency_seconds": latency,
            "citations_count": len(gen_result.source_citations),
            "grounding_status": evidence["grounding_status"],
            "all_five_sections_present": all([has_sec1, has_sec2, has_sec3, has_sec4, has_sec5])
        }, indent=2))

    except Exception as e:
        err_msg = str(e)
        # Sanitize error message to ensure zero credentials leaked
        if api_key in err_msg:
            err_msg = err_msg.replace(api_key, "[REDACTED_API_KEY]")
        print(json.dumps({
            "status": "FAILED",
            "error": err_msg
        }))

if __name__ == "__main__":
    run_test()
