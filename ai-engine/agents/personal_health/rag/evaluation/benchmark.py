"""Executable evaluation harness benchmarking Medical Knowledge RAG retrieval and generation metrics."""
import json
import math
import os
import sys
import time
from pathlib import Path
from typing import Dict, List, Any, Optional

# Ensure PYTHONPATH
sys.path.insert(0, os.path.abspath("ai-engine/agents"))
sys.path.insert(0, os.path.abspath("ai-engine"))

from personal_health.rag.service import MedicalKnowledgeRAGService
from personal_health.rag.schemas import RAGRetrievalStatus, GroundingStatus, RetrievalQuery

def compute_mrr(retrieved_doc_ids: List[str], expected_doc_ids: List[str]) -> float:
    for idx, doc_id in enumerate(retrieved_doc_ids, start=1):
        if any(exp.lower() in doc_id.lower() for exp in expected_doc_ids):
            return 1.0 / float(idx)
    return 0.0

def compute_ndcg_at_k(retrieved_doc_ids: List[str], expected_doc_ids: List[str], k: int = 3) -> float:
    dcg = 0.0
    for idx, doc_id in enumerate(retrieved_doc_ids[:k], start=1):
        rel = 1.0 if any(exp.lower() in doc_id.lower() for exp in expected_doc_ids) else 0.0
        dcg += rel / math.log2(idx + 1)
    
    # Ideal DCG
    ideal_rels = sorted([1.0] * min(len(expected_doc_ids), k), reverse=True)
    idcg = sum(rel / math.log2(idx + 1) for idx, rel in enumerate(ideal_rels, start=1))
    if idcg <= 0.0:
        return 1.0 if not expected_doc_ids else 0.0
    return dcg / idcg

def run_benchmark(dataset_path: Optional[Path] = None, output_path: Optional[Path] = None) -> Dict[str, Any]:
    dataset_file = dataset_path or Path(__file__).resolve().parent / "dataset.json"
    with open(dataset_file, "r", encoding="utf-8") as f:
        cases = json.load(f)

    rag = MedicalKnowledgeRAGService()

    precisions: List[float] = []
    recalls: List[float] = []
    mrrs: List[float] = []
    ndcgs: List[float] = []
    retrieval_latencies_ms: List[float] = []
    generation_latencies_ms: List[float] = []
    
    citation_correct_count = 0
    safety_violations_count = 0
    personal_isolation_success = 0
    personal_isolation_total = 0
    
    detailed_results: List[Dict[str, Any]] = []

    for c in cases:
        q_id = c["id"]
        q_text = c["query"]
        category = c["category"]
        expected_docs = c.get("expected_doc_ids", [])
        expected_cites = c.get("expected_citations", [])

        # Measure retrieval
        t0 = time.perf_counter()
        q_obj = RetrievalQuery(query_id=q_id, query_text=q_text, top_k=3)
        passages, status = rag.retriever.retrieve(q_obj)
        ret_ms = round((time.perf_counter() - t0) * 1000.0, 2)
        retrieval_latencies_ms.append(ret_ms)

        retrieved_doc_ids = [p.document_id for p in passages]
        retrieved_citations = [p.citation_reference for p in passages]

        # Evaluate personal record isolation
        if category == "personal_record_isolation":
            personal_isolation_total += 1
            if status in (RAGRetrievalStatus.NO_RELEVANT_SOURCES, RAGRetrievalStatus.INSUFFICIENT_EVIDENCE, RAGRetrievalStatus.ISOLATION_VIOLATION):
                personal_isolation_success += 1
            recalls.append(1.0 if not passages else 0.0)
            precisions.append(1.0 if not passages else 0.0)
            mrrs.append(1.0 if not passages else 0.0)
            ndcgs.append(1.0 if not passages else 0.0)

        # Evaluate no supporting evidence
        elif category == "no_supporting_evidence":
            if status in (RAGRetrievalStatus.NO_RELEVANT_SOURCES, RAGRetrievalStatus.INSUFFICIENT_EVIDENCE):
                precisions.append(1.0)
                recalls.append(1.0)
                mrrs.append(1.0)
                ndcgs.append(1.0)
            else:
                precisions.append(0.0)
                recalls.append(0.0)
                mrrs.append(0.0)
                ndcgs.append(0.0)

        # Factual / Multi-source queries
        else:
            if expected_docs:
                hits = sum(1 for d in retrieved_doc_ids if any(exp.lower() in d.lower() for exp in expected_docs))
                p_at_k = hits / float(len(passages)) if passages else 0.0
                r_at_k = min(1.0, hits / float(len(expected_docs)))
                mrr = compute_mrr(retrieved_doc_ids, expected_docs)
                ndcg = compute_ndcg_at_k(retrieved_doc_ids, expected_docs, k=3)
            else:
                p_at_k = 1.0 if not passages else 0.0
                r_at_k = 1.0 if not passages else 0.0
                mrr = 1.0 if not passages else 0.0
                ndcg = 1.0 if not passages else 0.0

            precisions.append(p_at_k)
            recalls.append(r_at_k)
            mrrs.append(mrr)
            ndcgs.append(ndcg)

        # Measure generation
        t_gen = time.perf_counter()
        gen_res = rag.generator.generate(query=q_text, passages=passages, retrieval_status=status)
        gen_ms = round((time.perf_counter() - t_gen) * 1000.0, 2)
        generation_latencies_ms.append(gen_ms)

        # Citation validation
        gen_cites = gen_res.source_citations
        if not gen_cites or all(any(gc in rc for rc in retrieved_citations) for gc in gen_cites):
            citation_correct_count += 1

        # Check safety & unsupported claims
        violations = gen_res.execution_metadata.get("violations", [])
        if violations:
            safety_violations_count += 1

        detailed_results.append({
            "case_id": q_id,
            "category": category,
            "query": q_text,
            "retrieval_status": status.value,
            "retrieved_count": len(passages),
            "retrieval_latency_ms": ret_ms,
            "generation_latency_ms": gen_ms,
            "grounding_status": gen_res.grounding_status.value,
            "violations": violations
        })

    summary = {
        "total_test_cases": len(cases),
        "mean_precision_at_3": round(sum(precisions) / len(precisions), 4),
        "mean_recall_at_3": round(sum(recalls) / len(recalls), 4),
        "mean_mrr": round(sum(mrrs) / len(mrrs), 4),
        "mean_ndcg_at_3": round(sum(ndcgs) / len(ndcgs), 4),
        "citation_correctness_pct": round((citation_correct_count / len(cases)) * 100.0, 2),
        "safety_violation_rate_pct": round((safety_violations_count / len(cases)) * 100.0, 2),
        "personal_isolation_rate_pct": round((personal_isolation_success / max(1, personal_isolation_total)) * 100.0, 2),
        "mean_retrieval_latency_ms": round(sum(retrieval_latencies_ms) / len(retrieval_latencies_ms), 2),
        "p95_retrieval_latency_ms": round(sorted(retrieval_latencies_ms)[int(len(retrieval_latencies_ms) * 0.95)], 2),
        "mean_generation_latency_ms": round(sum(generation_latencies_ms) / len(generation_latencies_ms), 2),
        "p95_generation_latency_ms": round(sorted(generation_latencies_ms)[int(len(generation_latencies_ms) * 0.95)], 2),
        "detailed_results": detailed_results
    }

    out_file = output_path or Path("scratch/medical_rag_evaluation_results.json")
    out_file.parent.mkdir(parents=True, exist_ok=True)
    with open(out_file, "w", encoding="utf-8") as f:
        json.dump(summary, f, indent=2)

    return summary

if __name__ == "__main__":
    res = run_benchmark()
    print("=" * 60)
    print("TRUSTLINE MEDICAL KNOWLEDGE RAG EVALUATION BENCHMARK")
    print("=" * 60)
    for k, v in res.items():
        if k != "detailed_results":
            print(f"{k}: {v}")
    print("=" * 60)
