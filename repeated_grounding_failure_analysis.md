# TRUSTLINE — Repeated LLM Grounding Failure Investigation Report

**Document ID:** `RAA-REPEATED-FAIL-2026-11-08`  
**Date:** 2026-11-08  
**Subject:** Comparative Root-Cause Investigation of Consecutive `LLM_GROUNDING_FAILED` Executions  
**Assessments Audited:**  
- **Primary (Latest):** `RA-0337F654` (Timestamp: `2026-11-08T19:23:50Z`)  
- **Comparator (Previous):** `RA-D9E05251` (Timestamp: `2026-11-08T18:08:10Z`)  
**Target Subsystem:** `ai-engine/agents/risk_assessment`  
**Auditor Role:** Senior Safety-Critical Software Auditor, Biomedical AI Validation Engineer & Clinical Decision Support Specialist  
**Investigation Mode:** Strict Read-Only Audit (Zero Modifications to Code, Prompts, Validators, Rules, or Reports)  
**Final Verdict:** **CONDITIONAL PASS**  
*(Deployment Pending Flight Surgeon Operational Review; Research Prototype — No Clinical Validation, Astronaut Operational Readiness, or NASA Operational Approval Claimed)*

---

## 1. Executive Summary

A comparative investigation was conducted across two consecutive executions of the **TRUSTLINE Risk Assessment Agent**:
- Assessment `RA-D9E05251`
- Assessment `RA-0337F654`

Both executions ingest the identical sensor and clinical profile dataset (`AST-001`, `SESSION-001`) and generate identical deterministic risk findings:
- `overall_risk: INSUFFICIENT_DATA`
- `overall_confidence: MODERATE`
- `coverage: 5/10 (0.50, PARTIAL)`
- `escalation: NO_TRIGGER_DETECTED` (Urgency: `NOMINAL`)
- `protective_factors: 1` (`PROT-RESP-01`)
- `uncertainties: 12`
- **`llm_status: LLM_GROUNDING_FAILED`**

Following `LLM_GROUNDING_FAILED`, both executions substitute the hardcoded **deterministic fallback** into `llm_explanation`.

### Key Investigation Takeaway:
1. **Both executions fail for the identical underlying cause:** The deterministic Risk Engine operates with 100% mathematical fidelity. However, the downstream `ClaimGroundingValidator` utilizes brittle, greedy regular expressions and naive substring matching that misclassify valid, boundary-compliant clinical synthesis as violations.
2. **The deterministic fallback itself contains factual inaccuracies and formatting defects:** Paragraph 2 asserts that evaluation reflects *"subjective inputs"*, despite subjective symptoms being completely unsubmitted in `SESSION-001`. Furthermore, punctuation assembly logic produces duplicate periods (`".."`) and semicolon artifacts (`".; "`).
3. **The deterministic fallback is emitted without self-validation:** When the fallback text was evaluated against `ClaimGroundingValidator.validate_synthesis()`, it **failed validation with 2 violations** due to regex bleed across unevaluated domain lists.

---

## 2. Section A: Comparative Analysis of Both Executions

| Execution Dimension | Assessment `RA-D9E05251` | Assessment `RA-0337F654` | Equivalence Verdict |
| :--- | :---: | :---: | :---: |
| **Assessment ID** | `RA-D9E05251` | `RA-0337F654` | Unique UUID |
| **Execution Timestamp** | `2026-11-08T18:08:10Z` | `2026-11-08T19:23:50Z` | Sequential Runs |
| **Deterministic Overall Risk** | `INSUFFICIENT_DATA` | `INSUFFICIENT_DATA` | **[VERIFIED IDENTICAL]** |
| **Evaluated Domains Risk** | `LOW` | `LOW` | **[VERIFIED IDENTICAL]** |
| **Overall Confidence** | `MODERATE` | `MODERATE` | **[VERIFIED IDENTICAL]** |
| **Domain Coverage Ratio** | `0.50 (5/10)` | `0.50 (5/10)` | **[VERIFIED IDENTICAL]** |
| **Evaluated Domains (5)** | CARDIO, RESP, PSYCH, THERM, DATA | CARDIO, RESP, PSYCH, THERM, DATA | **[VERIFIED IDENTICAL]** |
| **Unevaluated Domains (5)** | NEURO, SLEEP, FLUID, MUSCLE, GEN | NEURO, SLEEP, FLUID, MUSCLE, GEN | **[VERIFIED IDENTICAL]** |
| **Escalation State** | `NO_TRIGGER_DETECTED` | `NO_TRIGGER_DETECTED` | **[VERIFIED IDENTICAL]** |
| **Protective Factors** | 1 (`PROT-RESP-01`) | 1 (`PROT-RESP-01`) | **[VERIFIED IDENTICAL]** |
| **Identified Concerns** | 0 | 0 | **[VERIFIED IDENTICAL]** |
| **Uncertainties Count** | 12 | 12 | **[VERIFIED IDENTICAL]** |
| **LLM Inference Status** | `LLM_GROUNDING_FAILED` | `LLM_GROUNDING_FAILED` | **[VERIFIED IDENTICAL]** |
| **Emitted Synthesis Text** | Deterministic Fallback | Deterministic Fallback | **[VERIFIED IDENTICAL]** |

### Execution Pipeline Trace:
Both runs execute the exact same LangGraph pipeline ([`agent/agent.py:L33-L187`](file:///Users/alikhalidalikhalid/TRUSTLINE/ai-engine/agents/risk_assessment/agent/agent.py#L33-L187)):
1. `InputValidationService.validate_input()` passes (exit status clean).
2. `EvidenceNormalizationService.normalize_all()` generates 13 normalized evidence items.
3. `RiskEngine.evaluate_risks()` computes deterministic domain risks, 0.50 coverage, and 12 uncertainties.
4. `RiskEscalationService.determine_escalation()` assigns `NO_TRIGGER_DETECTED`.
5. `LLMInterpretationService.generate_explanation()` invokes Groq `llama-3.3-70b-versatile` with `temperature=0.1`.
6. `ClaimGroundingValidator.validate_synthesis()` returns `is_valid=False`.
7. `LLMInterpretationService` returns `(fallback_text, "LLM_GROUNDING_FAILED")`.

---

## 3. Section B: Exact Rejected Claim Identification

Every rejected claim pattern observed during empirical sampling on the `SESSION-001` prompt is cataloged below with exact source code references:

### Claim 1: Substring Negation Inversion (Symptom Status)
1. **Exact Claim Text:**  
   `"It is critical to note that unsubmitted symptom questionnaires and missing telemetry represent an unknown status, not a confirmed absence of symptoms or pathology."`
2. **Claim ID:** `REJ-CLAIM-SYM-01`
3. **Evidence IDs Expected:** `EV-SYM-CONFIRMED-ABSENCE`
4. **Evidence IDs Actually Matched:** `EV-SYM-UNSUBMITTED` (`validity_status: NOT_AVAILABLE`, `is_eligible_for_risk: False`)
5. **Validator Function:** `ClaimGroundingValidator.validate_synthesis`
6. **Exact Rejection Condition:**  
   [`services/claim_grounding_validator.py:L96-L106`](file:///Users/alikhalidalikhalid/TRUSTLINE/ai-engine/agents/risk_assessment/services/claim_grounding_validator.py#L96-L106)
   ```python
   if not symptoms_explicitly_denied:
       if (
           "denies symptoms" in lower
           or "denies any symptoms" in lower
           or "reported no symptoms" in lower
           or "confirmed absence of symptoms" in lower
           or "absence of symptoms confirmed" in lower
       ):
           violations.append(
               "Synthesis asserts unconfirmed symptom denial ('reported no symptoms' or 'denies symptoms') when symptoms were only unsubmitted."
           )
   ```
7. **Source File & Line Number:** `ai-engine/agents/risk_assessment/services/claim_grounding_validator.py`, Line 101.
8. **Finding Classification:** **`FALSE_POSITIVE`**  
   The LLM correctly stated the negation (*"not a confirmed absence of symptoms"*), strictly adhering to prompt instructions. The validator's naive substring check ignores the preceding negation (*"not a "*).

---

### Claim 2: Unbounded Greedy Regex Overreach (Overall Risk Low)
1. **Exact Claim Text:**  
   `"Consequently, the overall risk classification remains constrained by significant data gaps, and the current low-risk indicators in evaluated domains cannot be extrapolated to the unmonitored systems."`
2. **Claim ID:** `REJ-CLAIM-RISK-01`
3. **Evidence IDs Expected:** `DETERMINISTIC_OVERALL_RISK:INSUFFICIENT_DATA`
4. **Evidence IDs Actually Matched:** `DETERMINISTIC_OVERALL_RISK:INSUFFICIENT_DATA`, `EVALUATED_DOMAINS_RISK:LOW`
5. **Validator Function:** `ClaimGroundingValidator.validate_synthesis`
6. **Exact Rejection Condition:**  
   [`services/claim_grounding_validator.py:L66-L79`](file:///Users/alikhalidalikhalid/TRUSTLINE/ai-engine/agents/risk_assessment/services/claim_grounding_validator.py#L66-L79)
   ```python
   if overall_risk == RiskLevel.INSUFFICIENT_DATA:
       if (
           ...
           or re.search(r"overall\s+(?:physiological\s+|clinical\s+)?risk\b[^\.\n]*\blow\b", lower)
       ):
           violations.append(
               "Synthesis contradicts deterministic overall risk 'INSUFFICIENT_DATA' by declaring overall risk is low."
           )
   ```
7. **Source File & Line Number:** `ai-engine/agents/risk_assessment/services/claim_grounding_validator.py`, Line 75.
8. **Finding Classification:** **`FALSE_POSITIVE`**  
   The regex character class `[^\.\n]*` greedily spans across commas between clauses. The matched span was: `"overall risk classification remains constrained by significant data gaps, and the current low"`. The LLM explicitly upheld `INSUFFICIENT_DATA`, but the regex triggered an erroneous contradiction violation.

---

### Claim 3: Multi-Domain List Bleed (Unevaluated Domain Normality)
1. **Exact Claim Text (from Fallback):**  
   `"Unevaluated physiological domains (NEUROLOGICAL, SLEEP_AND_FATIGUE, HYDRATION_AND_FLUID_BALANCE, MUSCULOSKELETAL, GENERAL_PHYSIOLOGICAL) remain unmonitored and cannot be assumed nominal."`
2. **Claim ID:** `REJ-CLAIM-UNEV-01`
3. **Evidence IDs Expected:** `COVERAGE:UNEVALUATED_DOMAINS`
4. **Evidence IDs Actually Matched:** `COVERAGE:UNEVALUATED_DOMAINS`
5. **Validator Function:** `ClaimGroundingValidator.validate_synthesis`
6. **Exact Rejection Condition:**  
   [`services/claim_grounding_validator.py:L87-L95`](file:///Users/alikhalidalikhalid/TRUSTLINE/ai-engine/agents/risk_assessment/services/claim_grounding_validator.py#L87-L95)
   ```python
   if unevaluated_domains:
       for ud in unevaluated_domains:
           ud_clean = ud.lower().replace("_", " ")
           pattern = rf"\b{re.escape(ud_clean)}\b[^.\n]*(?:is|exhibits|shows|remains)?\s*(?:nominal|normal|healthy|low\s+risk|fully\s+intact)"
           if re.search(pattern, lower):
               violations.append(
                   f"Unevaluated domain '{ud}' improperly asserted as nominal/normal in clinical synthesis."
               )
   ```
7. **Source File & Line Number:** `ai-engine/agents/risk_assessment/services/claim_grounding_validator.py`, Line 90.
8. **Finding Classification:** **`FALSE_POSITIVE`**  
   Matches `"neurological, ... general_physiological) remain unmonitored and cannot be assumed nominal"`. The pattern bridges across the parenthetical list and ignores the negation `"cannot be assumed"`. This causes the system to reject its own fallback text.

---

### Claim 4: Candidate Protective Domain Gating (Nominal Parameter Check)
1. **Exact Claim Text:**  
   `"Cardiovascular risk is low and resting heart rate is nominal at 72.0 bpm."`
2. **Claim ID:** `REJ-CLAIM-PROT-01`
3. **Evidence IDs Expected:** `ALLOWED_PROTECTIVE_DOMAINS:['RESPIRATORY']`
4. **Evidence IDs Actually Matched:** `EV-PHY-HR-MEAN`
5. **Validator Function:** `ClaimGroundingValidator.validate_synthesis`
6. **Exact Rejection Condition:**  
   [`services/claim_grounding_validator.py:L108-L116`](file:///Users/alikhalidalikhalid/TRUSTLINE/ai-engine/agents/risk_assessment/services/claim_grounding_validator.py#L108-L116)
   ```python
   if allowed_protective_domains is not None:
       for cand in candidates:
           if cand not in allowed_lowers:
               pat = rf"\b{re.escape(cand)}\b[^.\n]*(?:is\s+protective|protective\s+factor|is\s+nominal\b|signal\s+fidelity\s+is\s+fully\s+verified)"
               if re.search(pat, lower):
                   violations.append(f"Synthesis asserts unverified protective factor for domain '{cand}'.")
   ```
7. **Source File & Line Number:** `ai-engine/agents/risk_assessment/services/claim_grounding_validator.py`, Line 113.
8. **Finding Classification:** **`FALSE_POSITIVE`**  
   The regex conflates describing a specific metric as nominal with asserting an unverified protective factor.

---

## 4. Section C: Deterministic Fallback Claims Audit

Detailed audit of the four specific statements in `_build_deterministic_fallback()` ([`services/llm_interpretation_service.py:L146-L195`](file:///Users/alikhalidalikhalid/TRUSTLINE/ai-engine/agents/risk_assessment/services/llm_interpretation_service.py#L146-L195)):

### Statement 1: "validated telemetry and subjective inputs"
- **Exact Text:** `"Domain-specific evaluation reflects validated telemetry and subjective inputs."`
- **Source Line:** Line 186 in `llm_interpretation_service.py`.
- **Classification:** **`FAILED` (Unsupported Claim in Fallback)**
- **Audit Analysis:** In `SESSION-001`, `pha_data.symptom_assessment_status` was `"NO_SYMPTOMS_REPORTED"` and `reported_symptoms = []`. Zero subjective symptom questionnaires were submitted. Asserting that the evaluation reflects "subjective inputs" is factually unsupported by session evidence.

### Statement 2: "No active clinical or operational alert rules were triggered"
- **Exact Text:** `"No active clinical or operational alert rules were triggered."`
- **Source Line:** Line 164 in `llm_interpretation_service.py`.
- **Classification:** **`VERIFIED` (With Severe Clinical Qualification)**
- **Audit Analysis:** The statement is technically true regarding `triggered_rules` (`len(triggered_rules) == 0`). However:
  - 5 out of 10 domains (Neurological, Hydration, Musculoskeletal, General Physiological, Psychological) have **ZERO registered rules** in `RuleRegistry`.
  - 4 out of the 10 registered rules could not be evaluated due to missing variables (`symptom_chest_pain`, `symptom_dyspnea`, `cabin_co2_percent`, `actual_sleep_hours`).
  - Stating that no alert rules triggered without explaining that half the systems lack rules creates a risk of false reassurance.

### Statement 3: "Protective factors noted" (`PROT-RESP-01`)
- **Exact Text:** `"Protective factors noted: Resting respiration rate (15.0 breaths/min) verified nominal within standard reference limits.."`
- **Source Line:** Line 167 in `llm_interpretation_service.py`.
- **Classification:** **`FAILED` (Scientifically Indefensible as a Protective Factor)**
- **Audit Analysis:** Resting respiration rate of 15.0 bpm is derived from chest-band RIP excursions. It satisfies NASA-STD-3001-VOL-1 nominal resting limits (10–20 bpm), indicating resting eupnea. However, eupnea confers **zero protective reserve** against hypoxia, hypercapnia, or EVA metabolic load. A single static measurement cannot establish pulmonary resilience. It should be re-classified as `WITHIN_NORMAL_LIMITS`.

### Statement 4: Repeated Uncertainties and Malformed Punctuation
- **Exact Functions Responsible:**
  1. **Punctuation Duplication (`".."` and `".; "`):**
     - Function: `LLMInterpretationService._build_deterministic_fallback` ([`services/llm_interpretation_service.py:L167, L175`](file:///Users/alikhalidalikhalid/TRUSTLINE/ai-engine/agents/risk_assessment/services/llm_interpretation_service.py#L167))
     - Mechanism: Strings in `protective_factors` and `uncertainties` already end with periods. Line 167 appends an extra period (`".."`), and Line 175 joins with `"; "` (`".; "`).
  2. **Uncertainty Repetition:**
     - Function: `RiskEngine.evaluate_risks` ([`services/risk_engine.py:L176, L377`](file:///Users/alikhalidalikhalid/TRUSTLINE/ai-engine/agents/risk_assessment/services/risk_engine.py#L176))
     - Mechanism: Line 176 appends an uncertainty for domain `GENERAL_PHYSIOLOGICAL`, and Line 377 appends an uncertainty for session-level unsubmitted symptoms, repeating the exact same medical limitation twice.
- **Classification:** **`FAILED` (Formatting & Redundancy Defect)**

---

## 5. Section D: Verification of Deterministic Results

All six deterministic values reported in `RA-0337F654` and `RA-D9E05251` were audited against actual engine state variables in `services/risk_engine.py`:

| Target Value | Evaluated State in Code | Source File & Line | Audit Classification |
| :--- | :--- | :--- | :---: |
| **5/10 Coverage** | `len(evaluated_domains) / len(all_domains) = 5 / 10 = 0.50` | `services/risk_engine.py:L382-L383` | **`VERIFIED`** |
| **INSUFFICIENT_DATA** | `concerns == [] and 0.0 < coverage_ratio < 1.0 -> INSUFFICIENT_DATA` | `services/risk_engine.py:L416` | **`VERIFIED`** |
| **MODERATE Confidence** | `coverage_ratio < 1.0 -> MODERATE` (also 4/5 evaluated domains MODERATE) | `services/risk_engine.py:L433` | **`VERIFIED`** |
| **NO_TRIGGER_DETECTED** | `triggered_rules == [] and overall_risk != CRITICAL -> NO_TRIGGER_DETECTED` | `services/escalation_service.py:L134` | **`VERIFIED`** |
| **1 Protective Factor** | `PROT-RESP-01` (Resting respiration 15.0 bpm within 10-20 bpm) | `services/risk_engine.py:L313-L326` | **`VERIFIED`** |
| **12 Uncertainties** | 5 unevaluated domains + 1 invalid HRV + 1 WESAD + 2 temp + 1 data qual + 1 symptom + 1 coverage | `services/risk_engine.py:L129-L436` | **`VERIFIED`** |

**Conclusion:** All six deterministic findings are mathematically and logically grounded in actual engine state.

---

## 6. Comprehensive Findings Classification

### VERIFIED
- **`VERIFIED`**: `RA-D9E05251` and `RA-0337F654` produce identical deterministic engine states across all 10 domains, coverage (0.50), confidence (`MODERATE`), and escalation (`NO_TRIGGER_DETECTED`).
- **`VERIFIED`**: The LLM did not hallucinate clinical diagnoses, unsupplied mission days, or unmonitored domain health in any execution.
- **`VERIFIED`**: The deterministic fallback is 100% repeatable and introduces zero autonomous clinical diagnoses.

### FAILED
- **`FAILED`**: `_build_deterministic_fallback()` claims the assessment reflects *"subjective inputs"*, which is false for `SESSION-001`.
- **`FAILED`**: `_build_deterministic_fallback()` punctuation formatting defects produce `".."` and `".; "` throughout.
- **`FAILED`**: `_build_deterministic_fallback()` is emitted unvalidated, and fails its own validator with 2 violations.
- **`FAILED`**: `PROT-RESP-01` is clinically indefensible as a "Protective Factor".

### FALSE_POSITIVE
- **`FALSE_POSITIVE`**: Substring check `"confirmed absence of symptoms"` rejects correct negation phrasing (*"not a confirmed absence of symptoms"*).
- **`FALSE_POSITIVE`**: Regex `overall...risk[^.\n]*low` matches across compound clauses separated by commas.
- **`FALSE_POSITIVE`**: Unevaluated domain regex `\b{ud}\b[^.\n]*nominal` matches across parenthetical lists, ignoring `"cannot be assumed"`.
- **`FALSE_POSITIVE`**: Candidate protective domain regex rejects statements noting specific vital signs are nominal.

### NOT_VERIFIED
- **`NOT_VERIFIED`**: Microgravity diagnostic sensitivity of chest-band RIP peak-counting algorithms against clinical gold-standard capnography ($EtCO_2$).

---

## 7. Recommended Safe Engineering Actions

1. **Syntactic Negation in Validator:** Replace naive substring matching with negative lookbehinds:
   ```python
   re.search(r"(?<!not\s(?:a\s)?)\bconfirmed absence of symptoms\b", lower)
   ```
2. **Clause-Bounded Risk Regex:** Bound the overall risk pattern by clause delimiters (commas, semicolons, dashes) to prevent cross-clause bridging:
   ```python
   re.search(r"overall\s+(?:physiological\s+|clinical\s+)?risk\b[^,;.\n]*\blow\b", lower)
   ```
3. **Punctuation Sanitization in Fallback:** Strip trailing periods before formatting f-strings in `_build_deterministic_fallback()`.
4. **Conditional Subjective Input Phrasing:** Condition paragraph 2 on whether symptoms were actually submitted:
   ```python
   f"Domain-specific evaluation reflects validated telemetry{' and subjective inputs' if symptoms_submitted else ''}."
   ```
5. **Aeromedical Taxonomy Adoption:** Re-classify `PROT-RESP-01` to `WITHIN_NORMAL_LIMITS`.

---

## 8. Final Verdict

```
+==============================================================================+
|                      TRUSTLINE RISK ASSESSMENT AGENT                         |
|            REPEATED LLM GROUNDING FAILURE AUDIT VERDICT                      |
|                                                                              |
|  Deterministic Risk Engine State:       [VERIFIED - INSUFFICIENT_DATA / MOD] |
|  Root-Cause Identification:             [ISOLATED - VALIDATOR FALSE POSITIVE]|
|  Fallback Subjective Input Claim:       [FAILED - UNSUPPORTED FACT IN STMT]  |
|  Fallback Punctuation/Formatting:       [FAILED - FORMATTING ARTIFACTS]      |
|  Fallback Self-Validation Test:         [FAILED - 2 FALSE POSITIVE REGEXES]  |
|                                                                              |
|  FINAL AUDIT VERDICT: CONDITIONAL PASS                                       |
|  (Pending Validator Regex Hardening & Flight Surgeon Operational Review)     |
+==============================================================================+
```

*Audited and Certified by:*  
**TRUSTLINE Safety-Critical AI Validation Team**  
*Date: 2026-11-08*
