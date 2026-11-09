# TRUSTLINE — Deterministic Fallback Integrity & Architecture Review

**Document ID:** `RAA-FALLBACK-REVIEW-2026-11-08`  
**Date:** 2026-11-08  
**Subject:** Scientific & Algorithmic Audit of Deterministic Fallback Synthesis in Risk Assessment  
**Target:** `_build_deterministic_fallback()` in [`ai-engine/agents/risk_assessment/services/llm_interpretation_service.py:L146-L195`](file:///Users/alikhalidalikhalid/TRUSTLINE/ai-engine/agents/risk_assessment/services/llm_interpretation_service.py#L146-L195)  
**System:** TRUSTLINE Spaceflight Health Risk Engine (Session SESSION-001, Assessment `RA-D9E05251`)  
**Auditor:** Senior Safety-Critical Software Auditor & Biomedical AI Validation Engineer  

---

## 1. Executive Summary & Purpose

In TRUSTLINE's multi-agent architecture, the **Risk Assessment Agent** utilizes an LLM (`llama-3.3-70b-versatile` via Groq) to synthesize clinical risk assessments into human-readable briefings for the Supervisor Agent and Flight Surgeon. If the LLM call fails, times out, or fails deterministic claim-grounding validation, the system deploys a hardcoded **deterministic fallback**.

In execution `RA-D9E05251`, the system reported `LLM_GROUNDING_FAILED` and emitted the deterministic fallback. This review audits the architectural integrity, determinism, punctuation artifacts, uncertainty duplication, and epistemic safety of this fallback mechanism.

---

## 2. Fallback Code Architecture & Data Flow

The fallback briefing is constructed in [`ai-engine/agents/risk_assessment/services/llm_interpretation_service.py`](file:///Users/alikhalidalikhalid/TRUSTLINE/ai-engine/agents/risk_assessment/services/llm_interpretation_service.py):

```python
# Lines 146-195 in services/llm_interpretation_service.py
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
    unevaluated_domains: Optional[List[str]] = None
) -> str:
    """Produce a guaranteed, grounded fallback briefing without LLM dependencies."""
    concerns_summary = (
        f"Active concerns identified: {', '.join(c.get('title', '') for c in concerns)}."
        if concerns else "No active clinical or operational alert rules were triggered."
    )
    protective_summary = (
        f"Protective factors noted: {'; '.join(protective_factors)}."
        if protective_factors else "No explicit protective factors documented."
    )
    uneval_note = (
        f"Unevaluated physiological domains ({', '.join(unevaluated_domains)}) remain unmonitored and cannot be assumed nominal. "
        if unevaluated_domains else ""
    )
    uncertainty_summary = (
        f"Observational caveats and uncertainties: {'; '.join(uncertainties)}."
        if uncertainties else "Telemetry completeness and signal integrity criteria were satisfied."
    )

    p1 = (
        f"Objective multi-agent risk assessment for Astronaut {astronaut_id} (Session {session_id}) "
        f"yields assessment status of {assessment_status} (domain coverage: {coverage_ratio:.2f}) with a "
        f"composite risk classification of {overall_risk.value} and {overall_confidence} evidential confidence. "
        f"Escalation status is evaluated as {escalation_state.value} ({escalation_reason})."
    )
    p2 = (
        f"Domain-specific evaluation reflects validated telemetry and subjective inputs. {concerns_summary} "
        f"{protective_summary}"
    )
    p3 = (
        f"Operational handling and limitations: {uneval_note}{uncertainty_summary} "
        "All findings represent automated deterministic evaluations for Supervisor Agent review and do not constitute independent medical diagnoses."
    )

    return f"{p1}\n\n{p2}\n\n{p3}"
```

---

## 3. Detailed Investigation of Fallback Properties

### 3.1 Why Uncertainties Are Repeated
In the fallback output of `RA-D9E05251`, 12 uncertainties are listed sequentially. Certain medical limitations appear in multiple variations:
1. **Unsubmitted Symptoms:**
   - Mention 1 (Line 176 in `risk_engine.py`): *"Domain GENERAL_PHYSIOLOGICAL is unevaluated: No eligible observational evidence or confirmed symptom reports submitted. Unsubmitted symptoms represent unknown symptom status."*
   - Mention 2 (Line 377 in `risk_engine.py`): *"Subjective symptoms were not submitted for this session; absence of reports does not establish clinical absence of symptoms."*
   - **Root Cause:** In `risk_engine.py`, the engine generates an uncertainty when a specific domain has zero eligible evidence (Line 176), and *separately* appends a symptom questionnaire status uncertainty (Line 377). When both are concatenated into `eval_res.uncertainties`, the same observational gap is articulated twice.
2. **Degraded Telemetry Attenuation:**
   - Mention 1 (Line 234 in `risk_engine.py`): *"Telemetry in domain THERMOREGULATORY is DEGRADED; evidential confidence attenuated to MODERATE."*
   - Mention 2 (Line 274 in `risk_engine.py`): *"Thermoregulatory telemetry reflects peripheral skin temperature, not core body temperature."*
   - Mention 3 (Line 234 in `risk_engine.py`): *"Telemetry in domain DATA_QUALITY_RELATED is DEGRADED; evidential confidence attenuated to MODERATE."*
   - **Root Cause:** Each domain evaluation block independently logs its diagnostic limitations and sensor quality attenuations into the global `uncertainties` list.

### 3.2 Why Punctuation Is Duplicated
Inspection of `llm_explanation` reveals distinct formatting anomalies:
- `"... reference limits.."` (Double period)
- `"... attenuated to MODERATE.; Domain NEUROLOGICAL is unevaluated: ..."` (Period followed by semicolon)
- `"... evaluated).. All findings represent ..."` (Double period after parenthesis)

**Root Cause:**
- Strings generated in `risk_engine.py` for `protective_factors` and `uncertainties` are formatted as complete grammatical sentences ending in a period (`.`):
  - `p.explanation`: `"Resting respiration rate (15.0 breaths/min) verified nominal within standard reference limits."`
  - `u`: `"Cardiovascular HRV RMSSD is INVALID (ZERO_VARIABILITY); autonomic cardiac regulation confidence attenuated to MODERATE."`
- In `_build_deterministic_fallback()`:
  - Line 167 appends an extra period: `f"Protective factors noted: {'; '.join(protective_factors)}."` &rarr; Result: `".."`
  - Line 175 joins items with `"; "` and appends a final period: `f"Observational caveats and uncertainties: {'; '.join(uncertainties)}."` &rarr; Result: `".; "` between items and `".."` at the end.

### 3.3 Is the Fallback Fully Deterministic?
- **Finding:** **VERIFIED (100% Deterministic)**
- **Evidence:**
  - `_build_deterministic_fallback()` relies entirely on deterministic Python string formatting (`f-strings`).
  - It contains zero calls to external APIs, random seeds, temperature sampling, or non-deterministic generators.
  - Given identical `RiskEvaluationResult` inputs, it produces byte-for-byte identical output on every execution.

### 3.4 Can Fallback Output Introduce Unsupported Claims?
- **Finding:** **VERIFIED (Zero Unsupported Claims Introduced)**
- **Evidence:**
  - The fallback strictly reflects the deterministic fields: `overall_risk.value` (`INSUFFICIENT_DATA`), `overall_confidence` (`MODERATE`), `coverage_ratio` (`0.50`), and `escalation_state.value` (`NO_TRIGGER_DETECTED`).
  - It explicitly states which domains are unevaluated and warns that they cannot be assumed nominal.
  - It contains no diagnostic statements, causal leaps, or hallucinated baseline comparisons.

---

## 4. Critical Architectural Finding: Fallback Self-Validation Failure

A critical question investigated was: **Is the fallback output validated by the Claim Grounding Validator before delivery?**

### 4.1 Execution Logic Trace
In [`services/llm_interpretation_service.py:L114-L126`](file:///Users/alikhalidalikhalid/TRUSTLINE/ai-engine/agents/risk_assessment/services/llm_interpretation_service.py#L114-L126):
```python
is_valid, violations = ClaimGroundingValidator.validate_synthesis(
    text=raw_text,
    overall_risk=overall_risk,
    ...
)
if not is_valid:
    return fallback_text, "LLM_GROUNDING_FAILED"
```
The fallback text is returned **directly** to the caller. It is **never** audited by `ClaimGroundingValidator.validate_synthesis()`.

### 4.2 Empirical Test of Fallback Against the Validator
When the actual fallback text from `RA-D9E05251` was passed into `ClaimGroundingValidator.validate_synthesis()`, the test returned:
```
IS_VALID: False
VIOLATIONS COUNT: 2
Violation 1: Unevaluated domain 'NEUROLOGICAL' improperly asserted as nominal/normal in clinical synthesis.
Violation 2: Unevaluated domain 'MUSCULOSKELETAL' improperly asserted as nominal/normal in clinical synthesis.
```

### 4.3 Why the Fallback Fails the Validator
The fallback text in Paragraph 3 contains:
> *"Unevaluated physiological domains (NEUROLOGICAL, SLEEP_AND_FATIGUE, HYDRATION_AND_FLUID_BALANCE, MUSCULOSKELETAL, GENERAL_PHYSIOLOGICAL) remain unmonitored and cannot be assumed nominal."*

In `ClaimGroundingValidator.validate_synthesis()` (Lines 87–95):
```python
pattern = rf"\b{re.escape(ud_clean)}\b[^.\n]*(?:is|exhibits|shows|remains)?\s*(?:nominal|normal|healthy|low\s+risk|fully\s+intact)"
```
- For `ud = 'NEUROLOGICAL'`:
  - `\bneurological\b` matches `"NEUROLOGICAL"`
  - `[^.\n]*` consumes `", SLEEP_AND_FATIGUE, HYDRATION_AND_FLUID_BALANCE, MUSCULOSKELETAL, GENERAL_PHYSIOLOGICAL) remain unmonitored and cannot be assumed "`
  - `nominal` matches `"nominal"`
- The regex **completely ignores the syntactic negation** (`cannot be assumed`) and spans across the entire parenthetical list.
- **Architectural Implication:** If the fallback were subjected to its own validator, the system would reject its own fallback due to a validator regex false positive.

---

## 5. Categorized Findings & Recommendations

### 5.1 VERIFIED Findings
1. **[VERIFIED] Deterministic Invariance:** The fallback text is mathematically deterministic and derives strictly from evaluated engine constants.
2. **[VERIFIED] Absence of Hallucinations:** The fallback introduces zero autonomous medical diagnoses, unverified protective factors, or causal extrapolations.
3. **[VERIFIED] Punctuation & Duplication Mechanisms:** Punctuation artifacts (`".."` and `".; "`) and repeated uncertainties are fully traced to f-string join logic and multi-source uncertainty appending in `risk_engine.py`.

### 5.2 FAILED Findings
1. **[FAILED] Punctuation Normalization:** `_build_deterministic_fallback()` fails to strip trailing periods before applying f-string separators, producing ungrammatical text.
2. **[FAILED] Uncertainty Deduplication:** `_build_deterministic_fallback()` does not deduplicate semantically overlapping uncertainty statements before joining.

### 5.3 FALSE POSITIVE Findings
1. **[FALSE POSITIVE] Fallback Self-Rejection:** `ClaimGroundingValidator` regex pattern `\b{ud}\b[^.\n]*nominal` produces false positive violations against the fallback's explicit warning: *"remain unmonitored and cannot be assumed nominal"*.

### 5.4 RECOMMENDATION Findings
1. **[RECOMMENDATION] Punctuation Sanitization:** In `_build_deterministic_fallback()`, strip trailing periods from items before joining:
   ```python
   clean_uncertainties = [u.rstrip(".") for u in uncertainties]
   uncertainty_summary = f"Observational caveats: {'; '.join(clean_uncertainties)}."
   ```
2. **[RECOMMENDATION] Semantic Uncertainty Deduplication:** Utilize an ordered set or semantic key deduplicator in `risk_engine.py` so that unsubmitted symptoms are not appended under both domain-level and session-level entries.
3. **[RECOMMENDATION] Regex Negation Boundary:** Modify the regex in `ClaimGroundingValidator` to prevent matching across negation boundaries (`cannot be assumed`, `not considered`, `never interpreted as`).
