"""CLI entrypoint for running the TRUSTLINE Sensor Quality Agent Validation Layer."""

import sys
import argparse
from pathlib import Path

cur = Path(__file__).resolve().parent
while cur != cur.parent:
    if (cur / "sensor_quality_agent").exists():
        if str(cur) not in sys.path:
            sys.path.insert(0, str(cur))
        break
    cur = cur.parent

try:
    from sensor_quality_agent.validation.validator_engine import ValidationEngine
    from sensor_quality_agent.validation.schemas import ValidationVerdict
except ImportError:
    from validator_engine import ValidationEngine
    from schemas import ValidationVerdict


def main() -> int:
    """Executes the validation pipeline and prints results summary."""
    parser = argparse.ArgumentParser(description="TRUSTLINE Sensor Quality Agent Validation Layer")
    parser.add_argument("--manifest", type=str, default=None, help="Path to session_manifest.json")
    parser.add_argument("--report", type=str, default=None, help="Path to sensor_quality_report.json")
    parser.add_argument("--base-dir", type=str, default=None, help="Base directory of sensor_quality_agent")
    args = parser.parse_args()

    engine = ValidationEngine(base_dir=args.base_dir)
    summary = engine.run_validation(manifest_path=args.manifest, report_path=args.report)

    sep = "=" * 70
    print("\n" + sep)
    print(" TRUSTLINE SENSOR QUALITY AGENT — INDEPENDENT VALIDATION AUDIT")
    print(sep)
    print(f" Final Verdict    : {summary.verdict.value}")
    print(f" Total Checks     : {summary.checks_run}")
    print(f" Checks Passed    : {summary.checks_passed}")
    print(f" Checks Warning   : {summary.checks_warned}")
    print(f" Checks Failed    : {summary.checks_failed}")
    print(sep)
    print(" SENSOR VALIDATION BREAKDOWN:")
    for s in summary.sensor_summaries.values():
        print(f"  - {s.sensor:5s} | Score: {s.quality_score:.4f} | Status: {s.status:23s} | Verdict: {s.verdict}")
    print(sep)
    if summary.critical_issues:
        print(f" Critical Issues  : {len(summary.critical_issues)} detected")
        for ci in summary.critical_issues[:3]:
            print(f"    * {ci}")
    else:
        print(" Critical Issues  : 0 (No safety invariant violations)")
    print(f" Deliverables Dir : {engine.output_dir}")
    print(sep + "\n")

    if summary.verdict in (ValidationVerdict.PASS, ValidationVerdict.CONDITIONAL_PASS):
        return 0
    return 1


if __name__ == "__main__":
    sys.exit(main())
