# TRUSTLINE — Deployment & Operations Guide

## 1. Environment & Hardware Prerequisites

- **Target Hardware**: Edge mission computer (Apple Silicon Mac Mini / Industrial ARM64 or x86_64 flight server).
- **Memory**: Minimum 8GB unified memory.
- **Python**: Version 3.10+ with virtual environment support.
- **Operating System**: macOS 12+ or Linux (Ubuntu 22.04 LTS / Debian 12 / Rocky Linux 9).

---

## 2. Installation & Setup

```bash
# 1. Clone repository and navigate to root
cd TRUSTLINE

# 2. Activate Python environment
python3 -m venv venv
source venv/bin/activate

# 3. Install core dependencies
pip install -r requirements.txt

# 4. Set environment paths
export PYTHONPATH=.:ai-agents:ai-engine/agents:ai-engine:data-engineering
export TRUSTLINE_DB_PATH=mission_data/trustline.db
```

---

## 3. Launching Mission Services

TRUSTLINE runs as a unified FastAPI service hosting the REST APIs, WebSocket feeds, and the modern 3D frontend SPA:

```bash
# Launch unified server on port 8000
python3 -m uvicorn backend.main:app --host 0.0.0.0 --port 8000 --workers 1
```

Once running:
- **Web Application**: Open `http://localhost:8000/` in any modern browser (Chrome, Safari, Firefox, Edge).
- **API Documentation**: Available at `http://localhost:8000/docs` (Swagger UI) and `http://localhost:8000/redoc`.
- **WebSocket Telemetry**: `ws://localhost:8000/ws/telemetry/{astronaut_id}?token={jwt_token}`.

---

## 4. Ground Synchronization Configuration

To enable Earth-ground telemetry synchronization when connectivity is available:

```bash
# Configure ground telemetry endpoint
export TRUSTLINE_GROUND_ENDPOINT="https://mission-control.nasa.gov/api/v1/sync"
export TRUSTLINE_SYNC_TOKEN="secret-ground-bearer-token"
export TRUSTLINE_SYNC_INTERVAL_SEC=30
```

When unconfigured, TRUSTLINE operates in truthful **Offline Buffer Mode**, queueing events locally in SQLite until link establishment.
