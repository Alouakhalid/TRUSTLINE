"""Report generation and formatting for explainability outputs."""
from typing import Dict, List
from ..schemas.output_schema import SensorQualityResult, OverallQuality

class ExplanationReportFormatter:
    """Formats explainability findings into human-readable and structured text."""

    @staticmethod
    def format_markdown_summary(
        overall: OverallQuality,
        sensor_results: Dict[str, SensorQualityResult]
    ) -> str:
        lines = [
            "** Sensor Quality Assessment Summary **",
            f"- **Overall Session Score:** {overall.score:.4f}",
            f"- **Mission Quality Status:** `{overall.status.value}`",
            f"- **Valid Sensors:** {overall.valid_sensors_count}/{overall.total_sensors_count}",
            ""
        ]

        if overall.degraded_sensors:
            lines.append(f"- **Degraded Sensors:** {', '.join(overall.degraded_sensors)}")
        if overall.rejected_sensors:
            lines.append(f"- **Rejected Sensors:** {', '.join(overall.rejected_sensors)}")
        lines.append("")

        lines.append("| Sensor | Score | Status | Recommendation | Top Issues |")
        lines.append("| :--- | :---: | :---: | :---: | :--- |")

        for sensor, res in sensor_results.items():
            top_issues = ", ".join([issue.reason_code for issue in res.issues[:2]]) or "None"
            lines.append(
                f"| **{sensor}** | {res.quality_score:.4f} | `{res.status.value}` | {res.recommendation} | {top_issues} |"
            )

        return "\n".join(lines)
