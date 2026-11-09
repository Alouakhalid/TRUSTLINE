"""Service coordinating Groq LLM synthesis, retries, and deterministic fallback generation."""
import os
import re
import time
from typing import Dict, List, Optional, Tuple, Any
from groq import Groq, APIError, APITimeoutError, RateLimitError

from ..config.settings import get_risk_settings
from ..schemas.risk_rules import RiskLevel, EscalationState
from ..agent.prompts import RISK_ASSESSMENT_SYSTEM_PROMPT, build_risk_user_prompt
from .claim_grounding_validator import ClaimGroundingValidator

class LLMInterpretationService:
    """Manages Groq LLM clinical risk explanations with deterministic grounding safety."""

    def __init__(
        self,
        api_key: Optional[str] = None,
        model: Optional[str] = None,
        timeout: Optional[float] = None,
        max_retries: int = 2
    ):
        cfg = get_risk_settings()
        self.api_key = api_key if api_key is not None else (cfg.groq_api_key or os.environ.get("GROQ_API_KEY", ""))
        self.model = model or cfg.groq_model
        self.timeout = timeout or cfg.groq_timeout
        self.max_retries = max_retries

        self._client: Optional[Groq] = None
        if self.api_key:
            self._client = Groq(api_key=self.api_key, timeout=self.timeout)

    def is_available(self) -> bool:
        """Check whether Groq credentials are configured."""
        return self._client is not None and bool(self.api_key)

    @classmethod
    def _deduplicate_and_normalize(cls, items: List[str]) -> List[str]:
        """Deduplicate text entries preserving insertion order and normalizing trailing punctuation."""
        seen = set()
        normalized = []
        for it in items:
            cleaned = it.strip().rstrip(".; ").strip()
            if not cleaned:
                continue
            norm_key = re.sub(r"\s+", " ", cleaned.lower())
            if norm_key not in seen:
                seen.add(norm_key)
                normalized.append(cleaned)
        return normalized

    def generate_explanation(
        self,
        astronaut_id: str,
        session_id: str,
        overall_risk: RiskLevel,
        overall_confidence: str,
        escalation_state: EscalationState,
        escalation_reason: str,
        domain_summaries: List[Dict[str, Any]],
        concerns: List[Dict[str, Any]],
        protective_factors: List[str],
        uncertainties: List[str],
        missing_info: Optional[List[str]] = None,
        mission_day_supplied: bool = False,
        assessment_status: str = "COMPLETED",
        coverage_ratio: float = 1.0,
        evaluated_domains: Optional[List[str]] = None,
        unevaluated_domains: Optional[List[str]] = None,
        symptoms_explicitly_denied: bool = False,
        allowed_protective_domains: Optional[List[str]] = None,
        symptoms_submitted: bool = False,
        nominal_observations: Optional[List[str]] = None,
        recommended_actions: Optional[List[Dict[str, Any]]] = None
    ) -> Tuple[str, str]:
        """Generate clinical explanation returning synthesis text and LLM status."""
        missing_info = missing_info or []
        fallback_text = self._build_deterministic_fallback(
            astronaut_id=astronaut_id,
            session_id=session_id,
            overall_risk=overall_risk,
            overall_confidence=overall_confidence,
            escalation_state=escalation_state,
            escalation_reason=escalation_reason,
            concerns=concerns,
            protective_factors=protective_factors,
            uncertainties=uncertainties,
            assessment_status=assessment_status,
            coverage_ratio=coverage_ratio,
            unevaluated_domains=unevaluated_domains,
            symptoms_submitted=symptoms_submitted,
            symptoms_explicitly_denied=symptoms_explicitly_denied,
            allowed_protective_domains=allowed_protective_domains,
            nominal_observations=nominal_observations
        )

        if not self.is_available():
            return fallback_text, "LLM_UNAVAILABLE"

        prompt = build_risk_user_prompt(
            astronaut_id=astronaut_id,
            session_id=session_id,
            overall_risk=overall_risk.value,
            overall_confidence=overall_confidence,
            escalation_state=escalation_state.value,
            escalation_reason=escalation_reason,
            domain_summaries=domain_summaries,
            concerns=concerns,
            protective_factors=protective_factors,
            uncertainties=uncertainties,
            missing_info=missing_info,
            assessment_status=assessment_status,
            coverage_ratio=coverage_ratio,
            evaluated_domains=evaluated_domains,
            unevaluated_domains=unevaluated_domains,
            recommended_actions=recommended_actions
        )

        attempt = 0
        backoff = 1.0
        while attempt <= self.max_retries:
            attempt += 1
            try:
                assert self._client is not None
                resp = self._client.chat.completions.create(
                    model=self.model,
                    messages=[
                        {"role": "system", "content": RISK_ASSESSMENT_SYSTEM_PROMPT},
                        {"role": "user", "content": prompt}
                    ],
                    temperature=0.1,
                    max_tokens=1024
                )
                raw_text = resp.choices[0].message.content or ""
                if not raw_text.strip():
                    return fallback_text, "LLM_INVALID_RESPONSE"

                is_valid, violations = ClaimGroundingValidator.validate_synthesis(
                    text=raw_text,
                    overall_risk=overall_risk,
                    escalation_state=escalation_state,
                    mission_day_supplied=mission_day_supplied,
                    assessment_status=assessment_status,
                    unevaluated_domains=unevaluated_domains,
                    symptoms_explicitly_denied=symptoms_explicitly_denied,
                    allowed_protective_domains=allowed_protective_domains
                )
                if not is_valid:
                    return fallback_text, "LLM_GROUNDING_FAILED"

                return raw_text.strip(), "LLM_SUCCESS"

            except APITimeoutError:
                if attempt > self.max_retries:
                    return fallback_text, "LLM_TIMEOUT"
                time.sleep(backoff)
                backoff *= 2.0
            except RateLimitError:
                if attempt > self.max_retries:
                    return fallback_text, "LLM_RATE_LIMIT"
                time.sleep(backoff)
                backoff *= 2.0
            except APIError:
                return fallback_text, "LLM_API_ERROR"
            except Exception:
                return fallback_text, "LLM_UNEXPECTED_ERROR"

        return fallback_text, "LLM_FAILED_RETRIES"

    def _build_deterministic_fallback(
        self,
        astronaut_id: str,
        session_id: str,
        overall_risk: RiskLevel,
        overall_confidence: str,
        escalation_state: EscalationState,
        escalation_reason: str,
        concerns: List[Dict[str, Any]],
        protective_factors: List[str],
        uncertainties: List[str],
        assessment_status: str = "COMPLETED",
        coverage_ratio: float = 1.0,
        unevaluated_domains: Optional[List[str]] = None,
        symptoms_submitted: bool = False,
        symptoms_explicitly_denied: bool = False,
        allowed_protective_domains: Optional[List[str]] = None,
        nominal_observations: Optional[List[str]] = None
    ) -> str:
        """Produce a guaranteed, grounded fallback briefing validated against grounding rules."""
        concerns_summary = (
            f"Active concerns identified: {', '.join(c.get('title', '') for c in concerns)}."
            if concerns else "No active alert rules were triggered across evaluated domains."
        )

        clean_protective = self._deduplicate_and_normalize(protective_factors)
        clean_nominal = self._deduplicate_and_normalize(nominal_observations or [])

        if clean_protective:
            protective_summary = f"Protective factors noted: {'; '.join(clean_protective)}."
        else:
            protective_summary = "No explicit protective factors documented."

        if clean_nominal:
            nominal_summary = f" Nominal observations within reference limits: {'; '.join(clean_nominal)}."
        else:
            nominal_summary = ""

        if unevaluated_domains:
            clean_uneval = [ud.strip().replace("_", " ") for ud in unevaluated_domains if ud.strip()]
            uneval_note = f"Unevaluated physiological domains ({', '.join(clean_uneval)}) remain unmonitored and cannot be assumed nominal. "
        else:
            uneval_note = ""

        deduped_unc = self._deduplicate_and_normalize(uncertainties)
        if deduped_unc:
            uncertainty_summary = f"Observational caveats and uncertainties: {'; '.join(deduped_unc)}."
        else:
            uncertainty_summary = "Telemetry completeness and signal integrity criteria were satisfied."

        p1 = (
            f"Objective multi-agent risk assessment for Astronaut {astronaut_id} (Session {session_id}) "
            f"yields assessment status of {assessment_status} (domain coverage: {coverage_ratio:.2f}) with a "
            f"composite risk classification of {overall_risk.value} and {overall_confidence} evidential confidence. "
            f"Escalation status is evaluated as {escalation_state.value} ({escalation_reason})."
        )

        if symptoms_submitted:
            p2_telemetry_clause = "Domain-specific evaluation reflects validated telemetry and subjective inputs."
        else:
            p2_telemetry_clause = "Domain-specific evaluation reflects validated telemetry (subjective symptom data was not submitted)."

        p2 = f"{p2_telemetry_clause} {concerns_summary} {protective_summary}{nominal_summary}"

        p3 = (
            f"Operational handling and limitations: {uneval_note}{uncertainty_summary} "
            "All findings represent automated deterministic evaluations for Supervisor Agent review and do not constitute independent medical diagnoses."
        )

        full_fallback = f"{p1}\n\n{p2}\n\n{p3}"

        is_valid, violations = ClaimGroundingValidator.validate_synthesis(
            text=full_fallback,
            overall_risk=overall_risk,
            escalation_state=escalation_state,
            mission_day_supplied=False,
            assessment_status=assessment_status,
            unevaluated_domains=unevaluated_domains,
            symptoms_explicitly_denied=symptoms_explicitly_denied,
            allowed_protective_domains=allowed_protective_domains
        )
        if not is_valid:
            p1_min = (
                f"Objective multi-agent risk assessment for Astronaut {astronaut_id} (Session {session_id}): "
                f"Assessment status {assessment_status} with composite risk {overall_risk.value} and {overall_confidence} evidential confidence."
            )
            p2_min = f"Escalation status is evaluated as {escalation_state.value} ({escalation_reason})."
            p3_min = "Automated deterministic summary generated under strict grounding validation constraints."
            return f"{p1_min}\n\n{p2_min}\n\n{p3_min}"

        return full_fallback
