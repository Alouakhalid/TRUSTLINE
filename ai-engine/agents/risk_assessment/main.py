"""Main CLI entrypoint and pipeline execution runner for TRUSTLINE Risk Assessment Agent."""
import argparse
import json
import os
import sys
from pathlib import Path
from typing import Dict, List, Optional, Any

if __package__ is None or __package__ == "":
    cur = Path(__file__).resolve().parent
    while cur != cur.parent:
        if (cur / "ai-engine").exists() or (cur / "risk_assessment").exists():
            if str(cur) not in sys.path:
                sys.path.insert(0, str(cur))
            break
        cur = cur.parent

from risk_assessment.config.settings import get_risk_settings
from risk_assessment.schemas.risk_input import RiskAssessmentInput
from risk_assessment.schemas.risk_output import RiskAssessmentOutput
from risk_assessment.agent.agent import RiskAssessmentAgent
from sensor_quality.schemas.output_schema import SensorQualityReport
from personal_health.schemas.assessment import PersonalHealthAssessment

def run_risk_assessment_pipeline(
    quality_report_path: Optional[str] = None,
    health_assessment_path: Optional[str] = None,
    astronaut_id: str = "AST-001",
    session_id: str = "SESSION-001",
    output_dir: str = ""
) -> int:
    """Execute end-to-end Risk Assessment Agent pipeline."""
    cfg = get_risk_settings()

    sqr_file = Path(quality_report_path).resolve() if quality_report_path else (
        cfg.sensor_quality_dir / "data" / "output" / "sensor_quality_report.json"
    )
    sqr_obj = None
    if sqr_file.exists():
        try:
            with open(sqr_file, "r", encoding="utf-8") as f:
                sqr_data = json.load(f)
            sqr_obj = SensorQualityReport.model_validate(sqr_data)
        except Exception as exc:
            sys.stderr.write(f"Warning: could not parse sensor quality report: {str(exc)}\n")

    pha_file = Path(health_assessment_path).resolve() if health_assessment_path else (
        cfg.personal_health_dir / "data" / "output" / "personal_health_assessment.json"
    )
    pha_obj = None
    if pha_file.exists():
        try:
            with open(pha_file, "r", encoding="utf-8") as f:
                pha_data = json.load(f)
            pha_obj = PersonalHealthAssessment.model_validate(pha_data)
        except Exception as exc:
            sys.stderr.write(f"Warning: could not parse personal health assessment: {str(exc)}\n")

    effective_astro_id = (
        pha_obj.astronaut_id if pha_obj else (sqr_obj.astronaut_id if sqr_obj else astronaut_id)
    )
    effective_session_id = (
        pha_obj.session_id if pha_obj else (sqr_obj.session_id if sqr_obj else session_id)
    )

    confirmed_recs = []
    try:
        from personal_health.services.medical_record_review_service import MedicalRecordReviewService
        rev_svc = MedicalRecordReviewService()
        confirmed_recs = rev_svc.get_confirmed_findings(effective_astro_id)
    except Exception:
        pass

    mission_ctx = pha_obj.mission_context if pha_obj else None

    payload = RiskAssessmentInput(
        astronaut_id=effective_astro_id,
        session_id=effective_session_id,
        sensor_quality_report=sqr_obj,
        personal_health_assessment=pha_obj,
        confirmed_medical_records=confirmed_recs,
        mission_context=mission_ctx
    )

    agent = RiskAssessmentAgent()
    output = agent.assess(payload)

    target_dir = Path(output_dir).resolve() if output_dir else cfg.output_dir
    target_dir.mkdir(parents=True, exist_ok=True)
    out_file = target_dir / "risk_assessment_report.json"
    with open(out_file, "w", encoding="utf-8") as f:
        f.write(output.model_dump_json(indent=2))
    try:
        from risk_assessment.services.claim_grounding_validator import ClaimGroundingValidator
    except ImportError:
        from .services.claim_grounding_validator import ClaimGroundingValidator
    trace_file = target_dir / "claim_grounding_trace.json"
    unev_dom_names = [d.value for d in output.coverage.unevaluated_domains]
    ClaimGroundingValidator.trace_claims(
        text=output.llm_explanation,
        overall_risk=output.overall_risk,
        escalation_state=output.escalation.state,
        mission_day_supplied=bool(mission_ctx and mission_ctx.mission_elapsed_time_hours is not None),
        assessment_status=output.assessment_status,
        unevaluated_domains=unev_dom_names,
        symptoms_explicitly_denied=any(p.factor_id == "PROT-SYM-DENIAL-01" for p in output.protective_factor_details),
        allowed_protective_domains=[p.domain.value for p in output.protective_factor_details],
        output_filepath=str(trace_file)
    )

    sys.stdout.write("=====================================================\n")
    sys.stdout.write("TRUSTLINE RISK ASSESSMENT AGENT REPORT\n")
    sys.stdout.write("=====================================================\n")
    sys.stdout.write(f"Assessment ID: {output.assessment_id}\n")
    sys.stdout.write(f"Astronaut: {output.astronaut_id} | Session: {output.session_id}\n")
    sys.stdout.write(f"Overall Risk: {output.overall_risk.value} | Confidence: {output.overall_confidence.value}\n")
    sys.stdout.write(f"Escalation State: {output.escalation.state.value} (Required: {output.escalation.required})\n")
    sys.stdout.write(f"Escalation Urgency: {output.escalation.urgency_level} | Destination: {output.escalation.destination.value}\n")
    sys.stdout.write(f"Escalation Reason: {output.escalation.reason}\n")
    sys.stdout.write(f"Identified Concerns ({len(output.identified_concerns)}):\n")
    for c in output.identified_concerns:
        sys.stdout.write(f"  - [{c.severity.value}] {c.title}: {c.description}\n")
    sys.stdout.write(f"Triggered Rules ({len(output.triggered_rules)}):\n")
    for r in output.triggered_rules:
        sys.stdout.write(f"  - {r.rule_id}: {r.rule_name} (Source: {r.rule_source})\n")
    sys.stdout.write(f"Nominal Observations ({len(output.nominal_observations)}):\n")
    for n in output.nominal_observations:
        sys.stdout.write(f"  - {n}\n")
    sys.stdout.write(f"Protective Factors ({len(output.protective_factors)}):\n")
    for p in output.protective_factors:
        sys.stdout.write(f"  - {p}\n")
    sys.stdout.write(f"Uncertainties & Limitations ({len(output.uncertainties)}):\n")
    for u in output.uncertainties:
        sys.stdout.write(f"  - {u}\n")
    if output.llm_explanation:
        sys.stdout.write("-----------------------------------------------------\n")
        sys.stdout.write(f"EXECUTIVE RISK SYNTHESIS ({output.llm_status}):\n")
        sys.stdout.write(f"{output.llm_explanation}\n")
    sys.stdout.write("-----------------------------------------------------\n")
    sys.stdout.write(f"Report JSON written to: {out_file}\n")
    sys.stdout.write(f"Claim Grounding Trace written to: {trace_file}\n")
    sys.stdout.write("=====================================================\n")

    return 0

def main():
    parser = argparse.ArgumentParser(description="TRUSTLINE Risk Assessment Agent CLI")
    parser.add_argument("--quality-report", type=str, default="", help="Path to sensor quality report JSON")
    parser.add_argument("--health-assessment", type=str, default="", help="Path to personal health assessment JSON")
    parser.add_argument("--astronaut-id", type=str, default="AST-001", help="Astronaut ID")
    parser.add_argument("--session-id", type=str, default="SESSION-001", help="Session ID")
    parser.add_argument("--output", type=str, default="", help="Output directory")

    args = parser.parse_args()
    return run_risk_assessment_pipeline(
        quality_report_path=args.quality_report,
        health_assessment_path=args.health_assessment,
        astronaut_id=args.astronaut_id,
        session_id=args.session_id,
        output_dir=args.output
    )

if __name__ == "__main__":
    sys.exit(main())
