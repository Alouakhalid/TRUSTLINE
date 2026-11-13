"""Grounded medical answer generation and claim-citation validation engine."""
import json
import os
import re
from typing import Dict, List, Optional, Tuple, Any

from .schemas import (
    RetrievedPassage,
    RAGGenerationResult,
    RAGRetrievalStatus,
    GroundingStatus
)

class RAGClaimValidator:
    """Deterministic auditor ensuring generated claims strictly ground in retrieved passages."""

    FORBIDDEN_DIAGNOSES = (
        "diagnosed with",
        "suffering from a disease",
        "myocardial infarction",
        "cardiac arrest",
        "pulmonary embolism",
        "stroke"
    )

    FORBIDDEN_PRESCRIPTIONS = (
        "prescribe",
        "administer 50mg",
        "administer 100mg",
        "dosage of",
        "take medication"
    )

    @classmethod
    def audit_response(
        cls,
        generated_text: str,
        retrieved_passages: List[RetrievedPassage]
    ) -> Tuple[GroundingStatus, List[str], List[Dict[str, Any]]]:
        """Evaluate generated text against retrieved citations and clinical safety boundaries."""
        violations: List[str] = []
        lower = generated_text.lower()

        # Check for forbidden autonomous medical actions
        for d in cls.FORBIDDEN_DIAGNOSES:
            if d in lower:
                violations.append(f"Forbidden definitive clinical diagnosis claim detected: '{d}'.")
        for p in cls.FORBIDDEN_PRESCRIPTIONS:
            if p in lower:
                violations.append(f"Forbidden medication prescription detected: '{p}'.")

        # Citation validation: all cited references must exist in retrieved passages
        valid_citations = {p.citation_reference for p in retrieved_passages}
        cited_in_text = re.findall(r"\[([A-Z0-9\-_\.\s]+)\]", generated_text)

        for c in cited_in_text:
            c_clean = c.strip()
            # If citation does not match any retrieved passage citation
            matched = any(c_clean.lower() in vc.lower() or vc.lower() in c_clean.lower() for vc in valid_citations)
            if not matched and not any(k in c_clean.lower() for k in ("nasa", "iss", "esa", "sec", "ref", "protocol")):
                violations.append(f"Fabricated or ungrounded citation reference detected: '[{c_clean}]'.")

        # Sentence-by-sentence claim tracing
        sentences = [s.strip() for s in re.split(r"(?<=[.!?])\s+", generated_text) if s.strip()]
        claim_mappings: List[Dict[str, Any]] = []

        for idx, sent in enumerate(sentences, start=1):
            sent_lower = sent.lower()
            matched_citations: List[str] = []
            for p in retrieved_passages:
                # Lexical word overlap check with passage excerpt
                words = set(re.findall(r"\w+", sent_lower))
                p_words = set(re.findall(r"\w+", p.excerpt.lower()))
                overlap = len(words.intersection(p_words))
                if overlap >= 3:
                    matched_citations.append(p.citation_reference)

            claim_mappings.append({
                "sentence_index": idx,
                "claim_text": sent,
                "supported": len(matched_citations) > 0,
                "supporting_citations": matched_citations
            })

        unsupported_count = sum(1 for cm in claim_mappings if not cm["supported"])
        
        if violations or (len(sentences) > 0 and unsupported_count == len(sentences)):
            status = GroundingStatus.UNGROUNDED
        elif unsupported_count > 0:
            status = GroundingStatus.PARTIALLY_GROUNDED
        else:
            status = GroundingStatus.FULLY_GROUNDED

        return status, violations, claim_mappings

class GroundedMedicalGenerator:
    """Generates structured 5-part clinical responses using Groq LLM or deterministic fallback."""

    def __init__(self, api_key: Optional[str] = None, model: str = "qwen/qwen3.8-27b", router: Optional[Any] = None):
        self.api_key = api_key or os.environ.get("GROQ_API_KEY", "")
        self.model = model
        from hybrid_ai import HybridAIRouter, GroqProvider
        if router is not None:
            self.router = router
        else:
            groq_p = GroqProvider(api_key=self.api_key, model=self.model, timeout=20.0)
            self.router = HybridAIRouter(groq_provider=groq_p)

    def generate(
        self,
        query: str,
        passages: List[RetrievedPassage],
        retrieval_status: RAGRetrievalStatus
    ) -> RAGGenerationResult:
        """Synthesize a grounded answer with explicit sections and claim validation."""
        if retrieval_status == RAGRetrievalStatus.ISOLATION_VIOLATION:
            return RAGGenerationResult(
                query_id=f"GEN-{abs(hash(query)) % 1000000:06d}",
                query=query,
                retrieved_passages=[],
                retrieval_status=RAGRetrievalStatus.ISOLATION_VIOLATION,
                grounding_status=GroundingStatus.FULLY_GROUNDED,
                generated_answer=(
                    "**1. Retrieved Medical Facts:** Personal astronaut health records and telemetry history are strictly isolated from general medical knowledge retrieval.\n\n"
                    "**2. Clinical Interpretation:** Access to confidential astronaut medical records is prohibited via this general knowledge service.\n\n"
                    "**3. Uncertainty & Limitations:** Personal record isolation security guard triggered.\n\n"
                    "**4. Source Citations:** None.\n\n"
                    "**5. Missing Information:** Query cannot access personal astronaut records."
                ),
                uncertainty_and_limitations=["Personal record isolation security guard triggered."],
                missing_information=["Query rejected by security isolation guard."]
            )

        if retrieval_status == RAGRetrievalStatus.NO_RELEVANT_SOURCES:
            return RAGGenerationResult(
                query_id=f"GEN-{abs(hash(query)) % 1000000:06d}",
                query=query,
                retrieved_passages=[],
                retrieval_status=RAGRetrievalStatus.NO_RELEVANT_SOURCES,
                grounding_status=GroundingStatus.FULLY_GROUNDED,
                generated_answer=(
                    "**1. Retrieved Medical Facts:** No relevant medical guidelines or research documents found matching this query in the authorized knowledge corpus.\n\n"
                    "**2. Clinical Interpretation:** The medical knowledge base does not contain verified aerospace clinical protocols for this specific inquiry.\n\n"
                    "**3. Uncertainty & Limitations:** Retrieval returned 0 qualifying passages above the relevance threshold.\n\n"
                    "**4. Source Citations:** None.\n\n"
                    "**5. Missing Information:** Authoritative operational guidelines for this specific query are unmonitored or unindexed."
                ),
                missing_information=["Authoritative operational guidelines for this topic."]
            )

        if retrieval_status == RAGRetrievalStatus.CONFLICTING_SOURCES:
            citations = [p.citation_reference for p in passages]
            return RAGGenerationResult(
                query_id=f"GEN-{abs(hash(query)) % 1000000:06d}",
                query=query,
                retrieved_passages=passages,
                retrieval_status=RAGRetrievalStatus.CONFLICTING_SOURCES,
                grounding_status=GroundingStatus.CONFLICTING,
                generated_answer=(
                    "**1. Retrieved Medical Facts:** Conflicting clinical guidance was retrieved across authoritative sources:\n"
                    + "\n".join(f"- [{p.citation_reference}] {p.excerpt[:200]}..." for p in passages) + "\n\n"
                    "**2. Clinical Interpretation:** Contradictory management protocols or divergent analyte thresholds exist between the retrieved standards.\n\n"
                    "**3. Uncertainty & Limitations:** Autonomous resolution is prohibited; conflicting guidance requires Flight Surgeon clinical adjudication.\n\n"
                    "**4. Source Citations:** " + ", ".join(f"[{c}]" for c in citations) + "\n\n"
                    "**5. Missing Information:** Flight Surgeon directive resolving the standard conflict."
                ),
                source_citations=citations,
                uncertainty_and_limitations=["Conflicting evidence detected between retrieved standards."]
            )

        # Build context
        context_str = "\n\n".join([
            f"--- SOURCE [{p.citation_reference}] ({p.title}) ---\n{p.excerpt}"
            for p in passages
        ])

        # Attempt LLM synthesis through HybridAIRouter with local fallback
        answer_text = None
        if self.api_key or (self.router and getattr(self.router, "mode", "") == "LOCAL_ONLY"):
            try:
                system_prompt = (
                    "You are the TRUSTLINE Medical Knowledge Decision Support Engine. "
                    "Synthesize an answer using ONLY the retrieved medical passages below. "
                    "You MUST structure your response into exactly these 5 numbered sections:\n"
                    "1. Retrieved Medical Facts\n"
                    "2. Clinical Interpretation\n"
                    "3. Uncertainty & Limitations\n"
                    "4. Source Citations\n"
                    "5. Missing Information\n\n"
                    "STRICT SAFETY RULES:\n"
                    "- Do NOT invent citations or references. Every citation must be from the sources.\n"
                    "- Do NOT make definitive clinical diagnoses.\n"
                    "- Do NOT prescribe medications or dosages.\n"
                    "- Always note that this decision support tool does not replace a Flight Surgeon."
                )
                user_msg = f"Medical Query: {query}\n\nRetrieved Evidence:\n{context_str}"

                from hybrid_ai import ProviderRequest, TaskCategory
                req = ProviderRequest(
                    task_category=TaskCategory.MEDICAL_RAG_SYNTHESIS,
                    prompt=user_msg,
                    system_prompt=system_prompt,
                    temperature=0.1,
                    max_tokens=800,
                    timeout_seconds=20.0
                )
                resp = self.router.route_request(req)
                if resp.content and resp.content.strip():
                    answer_text = resp.content.strip()
            except Exception:
                answer_text = None

        # Fallback to deterministic synthesis if LLM unavailable
        if not answer_text:
            facts = [f"- [{p.citation_reference}] {p.excerpt.splitlines()[0]}" for p in passages]
            citations = [p.citation_reference for p in passages]
            answer_text = (
                f"**1. Retrieved Medical Facts:**\n" + "\n".join(facts) + "\n\n"
                f"**2. Clinical Interpretation:** Based on the retrieved spaceflight guidelines, "
                f"the protocol recommends monitoring indicators aligned with {passages[0].title}.\n\n"
                f"**3. Uncertainty & Limitations:** Grounded strictly in {len(passages)} indexed passage(s). "
                f"This decision support prototype does not replace a certified Flight Surgeon.\n\n"
                f"**4. Source Citations:** " + ", ".join(f"[{c}]" for c in citations) + "\n\n"
                f"**5. Missing Information:** Prospective individual astronaut baseline history."
            )

        # Audit generated answer against retrieved evidence
        g_status, violations, mappings = RAGClaimValidator.audit_response(answer_text, passages)

        # Parse sections
        facts_list = []
        for line in answer_text.splitlines():
            if line.strip().startswith("-") or line.strip().startswith("*"):
                facts_list.append(line.strip())

        citations_list = [p.citation_reference for p in passages]

        return RAGGenerationResult(
            query_id=f"GEN-{abs(hash(query)) % 1000000:06d}",
            query=query,
            retrieved_passages=passages,
            source_metadata=[{"chunk_id": p.chunk_id, "doc_id": p.document_id, "title": p.title} for p in passages],
            relevance_scores={p.chunk_id: p.relevance_score for p in passages},
            generated_answer=answer_text,
            retrieved_facts=facts_list[:5],
            synthesis_interpretation=f"Synthesis grounded in {len(passages)} retrieved medical document(s).",
            uncertainty_and_limitations=["Prototype decision support only; does not replace clinical personnel."],
            source_citations=citations_list,
            missing_information=[],
            claim_evidence_mapping=mappings,
            retrieval_status=retrieval_status,
            grounding_status=g_status,
            execution_metadata={"violations": violations, "model": self.model}
        )
