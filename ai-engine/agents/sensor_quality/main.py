"""Main entrypoint for TRUSTLINE Sensor Quality Agent."""
import argparse
import json
import sys
from pathlib import Path
if __package__ is None or __package__ == "":
    cur = Path(__file__).resolve().parent
    while cur != cur.parent:
        if (cur / "sensor_quality_agent").exists():
            if str(cur) not in sys.path:
                sys.path.insert(0, str(cur))
            break
        cur = cur.parent
    from sensor_quality_agent.schemas.input_schema import AstronautHealthManifest
    from sensor_quality_agent.ingestion.signal_loader import SignalLoader
    from sensor_quality_agent.core.quality_engine import QualityEngine
    from sensor_quality_agent.services.report_builder import ReportBuilder
    from sensor_quality_agent.tools.langchain_tools import global_tool_store
    from sensor_quality_agent.config.settings import get_settings
    from sensor_quality_agent.agent.agent import generate_llm_briefing, run_sensor_quality_crew
else:
    from .schemas.input_schema import AstronautHealthManifest
    from .ingestion.signal_loader import SignalLoader
    from .core.quality_engine import QualityEngine
    from .services.report_builder import ReportBuilder
    from .tools.langchain_tools import global_tool_store
    from .config.settings import get_settings
    from .agent.agent import generate_llm_briefing, run_sensor_quality_crew

def run_sensor_quality_pipeline(
    manifest_path: str,
    run_crew: bool = False,
    output_dir: str = ""
) -> int:
    cfg = get_settings()
    manifest_file = Path(manifest_path).resolve()
    if not manifest_file.exists():
        candidate = Path(__file__).resolve().parent / manifest_path
        if candidate.exists():
            manifest_file = candidate

    if not manifest_file.exists():
        sys.stderr.write(f"Manifest file not found: {manifest_file}\n")
        return 1

    try:
        with open(manifest_file, "r", encoding="utf-8") as f:
            manifest_data = json.load(f)
        manifest = AstronautHealthManifest(**manifest_data)
    except Exception as exc:
        sys.stderr.write(f"Invalid input manifest: {str(exc)}\n")
        return 1

    base_dir = manifest_file.parent.parent
    loader = SignalLoader(base_dir=base_dir)

    try:
        streams = loader.load_all_sensors(manifest, mmap=True)
    except Exception as exc:
        sys.stderr.write(f"Failed to load raw signals: {str(exc)}\n")
        return 1

    global_tool_store.initialize_session(
        astronaut_id=manifest.metadata.astronaut_id,
        session_id=manifest.metadata.session_id
    )
    for s_name, s_data in streams.items():
        global_tool_store.store_stream(s_name, s_data)

    engine = QualityEngine()
    sensor_results, overall_quality, decision = engine.inspect_all_streams(streams)

    llm_explanation = None
    sensor_summary_lines = []
    for s_name, res in sensor_results.items():
        issues_str = "; ".join([f"{iss.reason_code} ({iss.severity.value})" for iss in res.issues]) or "None"
        sensor_summary_lines.append(f"{s_name}: Score={res.quality_score:.4f}, Status={res.status.value}, Recommendation={res.recommendation}, Issues=[{issues_str}]")
    sensor_summaries_text = "\n".join(sensor_summary_lines)
    overall_text = f"Score={overall_quality.score:.4f}, Status={overall_quality.status.value}, ValidSensors={overall_quality.valid_sensors_count}/{overall_quality.total_sensors_count}"

    if run_crew:
        try:
            crew_briefing = run_sensor_quality_crew(
                astronaut_id=manifest.metadata.astronaut_id,
                session_id=manifest.metadata.session_id
            )
            llm_explanation = {
                "source": "crewai_groq_agent",
                "briefing": crew_briefing
            }
        except Exception:
            briefing = generate_llm_briefing(
                astronaut_id=manifest.metadata.astronaut_id,
                session_id=manifest.metadata.session_id,
                overall_quality_str=overall_text,
                sensor_summaries_str=sensor_summaries_text
            )
            llm_explanation = {
                "source": "groq_direct_synthesizer",
                "briefing": briefing
            }
    else:
        briefing = generate_llm_briefing(
            astronaut_id=manifest.metadata.astronaut_id,
            session_id=manifest.metadata.session_id,
            overall_quality_str=overall_text,
            sensor_summaries_str=sensor_summaries_text
        )
        if briefing:
            llm_explanation = {
                "source": "groq_direct_synthesizer",
                "briefing": briefing
            }

    target_out = Path(output_dir).resolve() if output_dir else cfg.output_dir
    builder = ReportBuilder(output_dir=target_out)
    report = builder.build_report(
        manifest=manifest,
        streams=streams,
        sensor_results=sensor_results,
        overall_quality=overall_quality,
        decision=decision,
        llm_explanation=llm_explanation,
        save_file=True
    )

    sys.stdout.write("=====================================================\n")
    sys.stdout.write("TRUSTLINE SENSOR QUALITY ASSESSMENT REPORT\n")
    sys.stdout.write("=====================================================\n")
    sys.stdout.write(f"Astronaut: {report.astronaut_id} | Session: {report.session_id}\n")
    sys.stdout.write(f"Overall Quality Score: {report.overall_quality.score:.4f}\n")
    sys.stdout.write(f"Status: {report.overall_quality.status.value}\n")
    sys.stdout.write(f"Valid Sensors: {report.overall_quality.valid_sensors_count}/{report.overall_quality.total_sensors_count}\n")
    sys.stdout.write(f"Can Proceed Downstream: {report.processing_decision.can_proceed}\n")
    sys.stdout.write("-----------------------------------------------------\n")
    for s_name, res in report.sensors.items():
        sys.stdout.write(f"  [{s_name}] Score: {res.quality_score:.4f} | Status: {res.status.value} | Rec: {res.recommendation}\n")
    if report.llm_explanation and report.llm_explanation.get("briefing"):
        sys.stdout.write("-----------------------------------------------------\n")
        sys.stdout.write("EXECUTIVE BRIEFING (GROQ LLM):\n")
        sys.stdout.write(f"{report.llm_explanation['briefing']}\n")
    sys.stdout.write("=====================================================\n")

    return 0

def main():
    parser = argparse.ArgumentParser(description="TRUSTLINE Sensor Quality Agent CLI")
    parser.add_argument("--manifest", type=str, default="data/input/astronaut_health_data.json", help="Path to input manifest JSON")
    parser.add_argument("--run-crew", action="store_true", help="Execute CrewAI agent with Groq LLM")
    parser.add_argument("--output", type=str, default="", help="Directory to save report JSON and plots")

    args = parser.parse_args()
    return run_sensor_quality_pipeline(
        manifest_path=args.manifest,
        run_crew=args.run_crew,
        output_dir=args.output
    )

if __name__ == "__main__":
    sys.exit(main())
