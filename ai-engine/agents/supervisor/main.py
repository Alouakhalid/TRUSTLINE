"""Main CLI entrypoint for TRUSTLINE Supervisor Agent (LangGraph Orchestrator)."""
import argparse
import json
import sys
import uuid
from pathlib import Path

if __package__ is None or __package__ == "":
    cur = Path(__file__).resolve().parent
    while cur != cur.parent:
        if (cur / "ai-engine").exists() or (cur / "supervisor").exists():
            if str(cur) not in sys.path:
                sys.path.insert(0, str(cur))
            break
        cur = cur.parent

try:
    from supervisor.schemas.requests import SupervisorRequest, AstronautInput, InputModality
    from supervisor.workflow.graph import SupervisorWorkflowRunner
    from supervisor.config.settings import get_supervisor_settings
except ImportError:
    from .schemas.requests import SupervisorRequest, AstronautInput, InputModality
    from .workflow.graph import SupervisorWorkflowRunner
    from .config.settings import get_supervisor_settings

def run_supervisor_cli(
    manifest_path: str = "data/input/astronaut_health_data.json",
    astronaut_id: str = "AST-001",
    session_id: str = "SESSION-001",
    query_text: str = "",
    voice_path: str = "",
    output_dir: str = ""
) -> int:
    """Execute end-to-end multi-agent Supervisor workflow via CLI."""
    cfg = get_supervisor_settings()
    if output_dir:
        cfg.output_dir = Path(output_dir).resolve()
        cfg.output_dir.mkdir(parents=True, exist_ok=True)

    m_file = Path(manifest_path).resolve()
    if not m_file.exists():
        candidate = cfg.sensor_quality_dir / manifest_path
        if candidate.exists():
            m_file = candidate
        else:
            candidate2 = Path.cwd() / manifest_path
            if candidate2.exists():
                m_file = candidate2

    resolved_manifest = str(m_file) if m_file.exists() else None

    request = SupervisorRequest(
        request_id=f"REQ-{uuid.uuid4().hex[:8].upper()}",
        astronaut_id=astronaut_id,
        session_id=session_id,
        modality=InputModality.MULTIMODAL,
        input_data=AstronautInput(
            text_query=query_text or None,
            voice_audio_path=voice_path or None,
            sensor_manifest_path=resolved_manifest
        )
    )

    runner = SupervisorWorkflowRunner()
    result_state = runner.run_pipeline(request=request)

    final_assessment = result_state.get("final_assessment") or {}
    workflow_status = result_state.get("workflow_status", "UNKNOWN")
    overall_risk = result_state.get("overall_risk", "UNKNOWN")
    escalation_state = result_state.get("escalation_state", "UNKNOWN")
    agent_status_map = result_state.get("agent_execution_status") or {}

    sys.stdout.write("=====================================================\n")
    sys.stdout.write("TRUSTLINE SUPERVISOR AGENT — MULTI-AGENT EXECUTION\n")
    sys.stdout.write("=====================================================\n")
    sys.stdout.write(f"Workflow ID: {result_state.get('workflow_id')} | Status: {workflow_status}\n")
    sys.stdout.write(f"Assessment ID: {final_assessment.get('assessment_id', 'N/A')}\n")
    sys.stdout.write(f"Subject: {astronaut_id} | Session: {session_id}\n")
    sys.stdout.write(f"Overall Risk: {overall_risk} | Escalation: {escalation_state}\n")
    timing = final_assessment.get("timing_breakdown") or {}
    sys.stdout.write("-----------------------------------------------------\n")
    sys.stdout.write("AGENT EXECUTION STATUS:\n")
    for agent_name, st in agent_status_map.items():
        st_val = st.get("status") if isinstance(st, dict) else getattr(st, "status", "UNKNOWN")
        time_val = st.get("execution_time_ms", 0.0) if isinstance(st, dict) else getattr(st, "execution_time_ms", 0.0)
        label = " (overhead)" if agent_name == "supervisor" else ""
        sys.stdout.write(f"  • {agent_name:25s}: {st_val} ({time_val:.1f} ms{label})\n")
    sys.stdout.write("-----------------------------------------------------\n")
    sys.stdout.write("WORKFLOW TIMING AUDIT (WALL-CLOCK & NODE BREAKDOWN):\n")
    sys.stdout.write(f"  • workflow_total_execution_time_ms : {timing.get('workflow_total_execution_time_ms', 0.0):.1f} ms\n")
    sys.stdout.write(f"  • supervisor_overhead_time_ms      : {timing.get('supervisor_overhead_time_ms', 0.0):.1f} ms\n")
    sys.stdout.write(f"  • sensor_quality_execution_time_ms : {timing.get('sensor_quality_execution_time_ms', 0.0):.1f} ms\n")
    sys.stdout.write(f"  • personal_health_execution_time_ms: {timing.get('personal_health_execution_time_ms', 0.0):.1f} ms\n")
    sys.stdout.write(f"  • risk_assessment_execution_time_ms: {timing.get('risk_assessment_execution_time_ms', 0.0):.1f} ms\n")
    sys.stdout.write(f"  • evidence_validation_time_ms      : {timing.get('evidence_validation_time_ms', 0.0):.1f} ms\n")
    sys.stdout.write(f"  • final_synthesis_time_ms          : {timing.get('final_synthesis_time_ms', 0.0):.1f} ms\n")
    sys.stdout.write(f"  • persistence_time_ms              : {timing.get('persistence_time_ms', 0.0):.1f} ms\n")
    sys.stdout.write("-----------------------------------------------------\n")
    sys.stdout.write("ASTRONAUT-FACING RESPONSE:\n")
    sys.stdout.write(f"{result_state.get('final_response', 'No response generated.')}\n")
    sys.stdout.write("=====================================================\n")

    return 0 if workflow_status in ("COMPLETED", "PARTIALLY_COMPLETED") else 1

def main():
    parser = argparse.ArgumentParser(description="TRUSTLINE Supervisor Agent CLI")
    parser.add_argument("--manifest", type=str, default="data/input/astronaut_health_data.json", help="Path to biosensor manifest JSON")
    parser.add_argument("--astronaut", type=str, default="AST-001", help="Astronaut ID")
    parser.add_argument("--session", type=str, default="SESSION-001", help="Session ID")
    parser.add_argument("--query", type=str, default="", help="Optional text query or symptom")
    parser.add_argument("--voice", type=str, default="", help="Optional voice recording path")
    parser.add_argument("--output", type=str, default="", help="Output directory")

    args = parser.parse_args()
    return run_supervisor_cli(
        manifest_path=args.manifest,
        astronaut_id=args.astronaut,
        session_id=args.session,
        query_text=args.query,
        voice_path=args.voice,
        output_dir=args.output
    )

if __name__ == "__main__":
    sys.exit(main())
