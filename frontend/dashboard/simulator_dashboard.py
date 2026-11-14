"""Frontend entrypoint for the TRUSTLINE Sensor Simulation Observability Dashboard."""
import sys
from pathlib import Path

cur = Path(__file__).resolve().parent
while cur != cur.parent:
    if (cur / "data-engineering").exists():
        if str(cur / "data-engineering") not in sys.path:
            sys.path.insert(0, str(cur / "data-engineering"))
        if str(cur) not in sys.path:
            sys.path.insert(0, str(cur))
        break
    cur = cur.parent

try:
    from simulator.dashboard.dashboard_app import create_simulator_dashboard_app
except ImportError:
    from data_engineering.simulator.dashboard.dashboard_app import create_simulator_dashboard_app


def run_dashboard(port: int = 8050, debug: bool = False):
    """Launch the interactive dashboard server."""
    app = create_simulator_dashboard_app(port=port)
    app.run(port=port, debug=debug)


if __name__ == "__main__":
    run_dashboard()
