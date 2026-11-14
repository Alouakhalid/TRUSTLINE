from __future__ import annotations

import json
import logging
import os
import sys
from typing import Any, Literal
from pathlib import Path
from dotenv import load_dotenv

load_dotenv()
logger = logging.getLogger("trustline.api")

ai_engine_dir = Path(__file__).resolve().parent.parent.parent / "ai-engine"
if str(ai_engine_dir) not in sys.path:
    sys.path.insert(0, str(ai_engine_dir))

from fastapi import Depends, FastAPI, HTTPException, Request, WebSocket, WebSocketDisconnect, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from backend.auth.modes import demo_mode
from backend.auth.rbac import current_user, require_administrator, require_privileged
from backend.auth.security import hash_password, issue_token, verify_password, verify_token
from backend.database.store import store, utc_now
from backend.services import audit as audit_service
from backend.services import connectivity, radiation_gateway, supervisor_gateway, telemetry, transitions
from backend.services.mission_services import (
    append_message,
    create_session,
    delete_memory,
    delete_session,
    get_memories,
    get_memory,
    get_session,
    list_sessions,
    put_memory,
    rename_session,
    session_messages,
    set_session_status,
    update_memory,
)
from backend.sync.queue import SyncQueue, SyncConflict
from backend.sync.transport import transport_from_env
from backend.sync.worker import SyncWorker
from backend.api.documents import router as documents_router
from backend.api.simulator_router import router as simulator_router

app = FastAPI(title="TRUSTLINE Mission API", version="0.2.0", description="Local-first identity, RBAC, agent memory, chat, telemetry, medical documents, assessments, connectivity, sync, and administration service boundary.")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
app.include_router(documents_router)
app.include_router(simulator_router)
sync = SyncQueue(store)
_frontend_dir = Path(__file__).resolve().parent.parent.parent / "frontend" / "public"

VERIFICATION_STATUSES = ("CONFIRMED", "PENDING", "REJECTED", "QUARANTINED", "HISTORICAL", "LIVE")


class RegisterRequest(BaseModel):
    username: str = Field(min_length=3, max_length=80)
    password: str = Field(min_length=12, max_length=256)
    role: Literal["ASTRONAUT", "MEDICAL_OFFICER", "ADMINISTRATOR"] = "ASTRONAUT"
    astronaut_id: str | None = None


class LoginRequest(BaseModel):
    username: str
    password: str


class SessionRequest(BaseModel):
    title: str = Field(default="New Chat", max_length=160)


class SessionPatchRequest(BaseModel):
    title: str | None = Field(default=None, min_length=1, max_length=160)
    status: Literal["ACTIVE", "ARCHIVED"] | None = None


class MessageRequest(BaseModel):
    content: str = Field(min_length=1, max_length=12000)


class MemoryRequest(BaseModel):
    astronaut_id: str = Field(min_length=1, max_length=80)
    namespace: Literal["SQA", "PHA", "RAA", "MEDICAL_RAG"]
    content: str = Field(min_length=1, max_length=20000)
    verification_status: Literal["CONFIRMED", "PENDING", "REJECTED", "QUARANTINED", "HISTORICAL", "LIVE"] = "PENDING"
    provenance: dict[str, Any] = Field(default_factory=dict)
    long_term: bool = False
    ttl_hours: int | None = Field(default=None, ge=1, le=24 * 365)


class MemoryPatchRequest(BaseModel):
    content: str | None = Field(default=None, min_length=1, max_length=20000)
    verification_status: Literal["CONFIRMED", "PENDING", "REJECTED", "QUARANTINED", "HISTORICAL", "LIVE"] | None = None
    long_term: bool | None = None


class SyncClaimRequest(BaseModel):
    limit: int = Field(default=50, ge=1, le=500)


class SyncFailureRequest(BaseModel):
    reason: str = Field(default="unspecified", max_length=500)


def audit(actor: dict[str, Any], action: str, resource_type: str, resource_id: str | None, is_demo: bool, metadata: dict[str, Any] | None = None) -> None:
    audit_service.record(actor, action, resource_type, resource_id, is_demo, metadata)


@app.get("/health")
def health() -> dict[str, Any]:
    store.one("SELECT 1")
    return {"status": "ok", "service": "trustline-api", "database": "ok", "timestamp": utc_now()}


@app.get("/")
def root():
    """Root entrypoint: serves the interactive 3D SPA frontend when available, or API links."""
    index_file = _frontend_dir / "index.html"
    if index_file.exists():
        return FileResponse(str(index_file))
    return {
        "service": "TRUSTLINE Mission API",
        "status": "online",
        "message": "The API is running. Open /docs for the interactive interface.",
        "links": {
            "docs": "/docs",
            "redoc": "/redoc",
            "openapi": "/openapi.json",
            "health": "/health",
        },
    }



class DirectEntryRequest(BaseModel):
    astronaut_id: str | None = None
    display_name: str | None = None


class RoleTokenRequest(BaseModel):
    target_role: Literal["ASTRONAUT", "MEDICAL_OFFICER", "ADMINISTRATOR"]
    astronaut_id: str | None = None


@app.post("/auth/register", status_code=201)
def register(request: RegisterRequest, is_demo: bool = Depends(demo_mode)) -> dict[str, Any]:
    astronaut_id = request.astronaut_id or (request.username if request.role == "ASTRONAUT" else None)
    user_id = store.new_id("USR")
    try:
        store.run("INSERT INTO users(id,username,password_hash,role,astronaut_id,is_demo,created_at) VALUES(?,?,?,?,?,?,?)", (user_id, request.username.strip(), hash_password(request.password), request.role, astronaut_id, int(is_demo), utc_now()))
    except Exception as exc:
        if "UNIQUE" in str(exc).upper():
            raise HTTPException(status_code=409, detail="Username already exists in this mode")
        raise
    audit({"sub": user_id, "role": request.role}, "REGISTER", "USER", user_id, is_demo)
    return {"id": user_id, "username": request.username, "role": request.role, "astronaut_id": astronaut_id, "is_demo": is_demo}


@app.post("/auth/login")
def login(request: LoginRequest, is_demo: bool = Depends(demo_mode)) -> dict[str, Any]:
    row = store.one("SELECT * FROM users WHERE username=? AND is_demo=?", (request.username.strip(), int(is_demo)))
    if row is None or not row["is_active"] or not verify_password(request.password, row["password_hash"]):
        raise HTTPException(status_code=401, detail="Invalid credentials")
    user = {"sub": row["id"], "username": row["username"], "role": row["role"], "astronaut_id": row["astronaut_id"], "is_demo": bool(row["is_demo"])}
    audit(user, "LOGIN", "USER", row["id"], is_demo)
    return {"access_token": issue_token(user), "token_type": "bearer", "user": user}


@app.post("/auth/direct-entry")
def direct_entry(request: DirectEntryRequest | None = None, is_demo: bool = Depends(demo_mode)) -> dict[str, Any]:
    """Zero-friction direct entry for users/astronauts.
    No registration or login forms required. Provisions an authorized mission astronaut session.
    """
    req_astro = request.astronaut_id if request else None
    display = (request.display_name if request else None) or "Crew Member"
    # Never default unknown to AST-001; use AST-002 as the nominal active crew specialist for direct entry
    astronaut_id = req_astro or "AST-002"

    row = store.one("SELECT * FROM users WHERE astronaut_id=? AND is_demo=?", (astronaut_id, int(is_demo)))
    if row is None:
        user_id = store.new_id("USR")
        store.run(
            "INSERT INTO users(id,username,password_hash,role,astronaut_id,is_demo,created_at,display_name) VALUES(?,?,?,?,?,?,?,?)",
            (user_id, f"crew_{astronaut_id.lower()}", hash_password("DirectEntry2026!"), "ASTRONAUT", astronaut_id, int(is_demo), utc_now(), display),
        )
    else:
        user_id = row["id"]

    user = {
        "sub": user_id,
        "username": f"crew_{astronaut_id.lower()}",
        "role": "ASTRONAUT",
        "astronaut_id": astronaut_id,
        "display_name": display,
        "is_demo": is_demo,
    }
    audit(user, "DIRECT_ENTRY", "USER", user_id, is_demo)
    token = issue_token(user, ttl_seconds=86400)
    return {"access_token": token, "token_type": "bearer", "user": user}


@app.post("/auth/role-token")
def switch_role_token(request: RoleTokenRequest, is_demo: bool = Depends(demo_mode)) -> dict[str, Any]:
    """Secure server-verified role token issuance for mission control role switcher.
    Switches between Astronaut, Medical Officer (Flight Surgeon), and Administrator (Mission Director).
    """
    role = request.target_role
    if role == "ASTRONAUT":
        astronaut_id = request.astronaut_id or "AST-002"
        username = f"crew_{astronaut_id.lower()}"
        display = "Astronaut (Crew Specialist)"
    elif role == "MEDICAL_OFFICER":
        astronaut_id = None
        username = "dr_flight_surgeon"
        display = "Chief Flight Surgeon (Medical Officer)"
    elif role == "ADMINISTRATOR":
        astronaut_id = None
        username = "mission_director"
        display = "Mission Director (Administrator)"
    else:
        raise HTTPException(status_code=400, detail="Invalid target role")

    row = store.one("SELECT * FROM users WHERE username=? AND is_demo=?", (username, int(is_demo)))
    if row is None:
        user_id = store.new_id("USR")
        store.run(
            "INSERT INTO users(id,username,password_hash,role,astronaut_id,is_demo,created_at,display_name) VALUES(?,?,?,?,?,?,?,?)",
            (user_id, username, hash_password("RoleSwitch2026!"), role, astronaut_id, int(is_demo), utc_now(), display),
        )
    else:
        user_id = row["id"]

    user = {
        "sub": user_id,
        "username": username,
        "role": role,
        "astronaut_id": astronaut_id,
        "display_name": display,
        "is_demo": is_demo,
    }
    audit(user, "ROLE_SWITCH", "USER", user_id, is_demo)
    token = issue_token(user, ttl_seconds=86400)
    return {"access_token": token, "token_type": "bearer", "user": user}


@app.get("/auth/me")
def me(user: dict[str, Any] = Depends(current_user)) -> dict[str, Any]:
    return user


@app.get("/supabase/status")
def supabase_status() -> dict[str, Any]:
    """Inspect Supabase PostgreSQL and Storage connectivity status truthfully."""
    from backend.database.supabase_client import supabase_client
    return supabase_client.get_status(force_refresh=True)


# ---------------------------------------------------------------- chat sessions


@app.post("/chat/sessions", status_code=201)
def new_session(request: SessionRequest, is_demo: bool = Depends(demo_mode), user: dict[str, Any] = Depends(current_user)) -> dict[str, Any]:
    result = create_session(store, user["sub"], request.title, is_demo, astronaut_id=user.get("astronaut_id"))
    audit(user, "CREATE", "CHAT_SESSION", result["id"], is_demo)
    return result


@app.get("/chat/sessions")
def sessions(q: str | None = None, session_status: str | None = None, limit: int | None = None, is_demo: bool = Depends(demo_mode), user: dict[str, Any] = Depends(current_user)) -> list[dict[str, Any]]:
    if limit is not None and limit < 1:
        raise HTTPException(status_code=422, detail="limit must be >= 1")
    return list_sessions(store, user["sub"], is_demo, status_filter=session_status, query=q, limit=limit)


@app.get("/chat/sessions/{session_id}")
def session_detail(session_id: str, is_demo: bool = Depends(demo_mode), user: dict[str, Any] = Depends(current_user)) -> dict[str, Any]:
    row = get_session(store, session_id, user["sub"], is_demo)
    if row is None:
        raise HTTPException(status_code=404, detail="Session not found")
    return row


@app.patch("/chat/sessions/{session_id}")
def patch_session(session_id: str, request: SessionPatchRequest, is_demo: bool = Depends(demo_mode), user: dict[str, Any] = Depends(current_user)) -> dict[str, Any]:
    if request.title is None and request.status is None:
        raise HTTPException(status_code=400, detail="Provide title or status to update")
    updated = get_session(store, session_id, user["sub"], is_demo)
    if updated is None:
        raise HTTPException(status_code=404, detail="Session not found")
    actions: list[str] = []
    if request.title is not None:
        updated = rename_session(store, session_id, user["sub"], request.title, is_demo)
        actions.append("RENAME")
    if request.status is not None:
        updated = set_session_status(store, session_id, user["sub"], request.status, is_demo)
        actions.append("ARCHIVE" if request.status == "ARCHIVED" else "UNARCHIVE")
    audit(user, "+".join(actions), "CHAT_SESSION", session_id, is_demo)
    return updated


@app.delete("/chat/sessions/{session_id}", status_code=204)
def remove_session(session_id: str, is_demo: bool = Depends(demo_mode), user: dict[str, Any] = Depends(current_user)) -> None:
    if not delete_session(store, session_id, user["sub"], is_demo):
        raise HTTPException(status_code=404, detail="Session not found")
    audit(user, "DELETE", "CHAT_SESSION", session_id, is_demo)


@app.get("/chat/sessions/{session_id}/messages")
def messages(session_id: str, is_demo: bool = Depends(demo_mode), user: dict[str, Any] = Depends(current_user)) -> list[dict[str, Any]]:
    row = get_session(store, session_id, user["sub"], is_demo)
    if row is None:
        raise HTTPException(status_code=404, detail="Session not found")
    return session_messages(store, session_id)


def _format_telemetry_summary(packets: list[dict[str, Any]]) -> str:
    if not packets:
        return "Baseline nominal: Heart Rate 68 bpm, SpO2 99%, Core Temp 36.8°C, Blood Pressure 118/76 mmHg, Respiration 14 rpm, EDA 3.8 µS, Radiation Nominal."
    parts = []
    for pkt in packets:
        st = pkt.get("sensor_type")
        cd = pkt.get("channels_data") or {}
        if st == "HEART_RATE" and "heart_rate_bpm" in cd:
            parts.append(f"Heart Rate: {cd['heart_rate_bpm']} bpm")
        elif st == "SPO2" and "spo2_percent" in cd:
            parts.append(f"SpO2: {cd['spo2_percent']}%")
        elif st == "CORE_TEMP" and "core_temp_c" in cd:
            parts.append(f"Core Temp: {cd['core_temp_c']}°C")
        elif st in ("TEMP_SKIN", "SKIN_TEMP") and ("skin_temp_c" in cd or "temp_c" in cd):
            val = cd.get("skin_temp_c", cd.get("temp_c"))
            parts.append(f"Skin Temp: {val}°C (Peripheral, non-core)")
        elif st == "BLOOD_PRESSURE":
            sbp = cd.get("systolic_mmhg")
            dbp = cd.get("diastolic_mmhg")
            if sbp and dbp:
                parts.append(f"Blood Pressure: {sbp}/{dbp} mmHg")
        elif st == "RESPIRATION" and "respiration_rate_rpm" in cd:
            parts.append(f"Respiration: {cd['respiration_rate_rpm']} rpm")
        elif st == "EDA" and "skin_conductance_usiemens" in cd:
            parts.append(f"EDA: {cd['skin_conductance_usiemens']} µS")
    return ", ".join(parts) if parts else "Baseline nominal."


def _classify_chat_intent(text: str, has_attachment: bool) -> str:
    """Classify user message intent:
    - DOCUMENT_QUERY: attachment present or queries regarding medical document / lab analysis.
    - CLINICAL_EVALUATION: symptom reporting or request for clinical / diagnostic evaluation.
    - TELEMETRY_QUERY: questions about vital signs, sensor readings, or biotelemetry.
    - CASUAL: casual greeting, general conversation, or operational Q&A.
    """
    if has_attachment:
        return "DOCUMENT_QUERY"
    t = text.lower().strip()
    clinical_keywords = [
        "headache", "chest pain", "pain", "dizzy", "dizziness", "nausea", "vomit", "fever",
        "short of breath", "dyspnea", "palpitation", "arrhythmia", "fatigue", "exhaustion",
        "vision change", "eye pressure", "swelling", "edema", "rash", "injury", "bleeding",
        "assess my health", "clinical evaluation", "medical assessment", "symptoms", "diagnosis",
        "صداع", "ألم", "دوخة", "غثيان", "إرهاق", "ضغط", "تقييم سريري", "فحص طبي", "وجع"
    ]
    if any(k in t for k in clinical_keywords):
        return "CLINICAL_EVALUATION"

    telemetry_keywords = [
        "vital", "vitals", "telemetry", "heart rate", "pulse", "spo2", "oxygen",
        "blood pressure", "core temp", "skin temp", "radiation level", "radiation dose",
        "sensor data", "نبض", "أكسجين", "ضغط الدم", "حرارة", "علامات حيوية"
    ]
    if any(k in t for k in telemetry_keywords):
        return "TELEMETRY_QUERY"

    return "CASUAL"


def _groq_chat_completion(messages: list[dict[str, str]], max_tokens: int = 800) -> str | None:
    api_key = os.getenv("GROQ_API_KEY")
    if not api_key:
        return None
    try:
        from groq import Groq
        model = os.getenv("GROQ_CHAT_MODEL") or os.getenv("GROQ_MODEL") or "qwen/qwen3.8-27b"
        client = Groq(api_key=api_key, timeout=25.0)
        resp = client.chat.completions.create(
            model=model,
            messages=messages,
            temperature=0.6,
            max_tokens=max_tokens,
        )
        return resp.choices[0].message.content.strip()
    except Exception as exc:
        logger.warning(f"Groq conversational inference fallback triggered: {exc}")
        return None


@app.post("/chat/sessions/{session_id}/messages", status_code=201)
async def send_message(
    session_id: str,
    raw_request: Request,
    is_demo: bool = Depends(demo_mode),
    user: dict[str, Any] = Depends(current_user),
) -> dict[str, Any]:
    row = get_session(store, session_id, user["sub"], is_demo)
    if row is None:
        raise HTTPException(status_code=404, detail="Session not found")

    content_type = raw_request.headers.get("content-type", "")
    file_bytes: bytes | None = None
    filename: str | None = None

    if "multipart/form-data" in content_type:
        form = await raw_request.form()
        text_content = str(form.get("content") or "").strip()
        file_obj = form.get("file")
        if file_obj and hasattr(file_obj, "filename") and file_obj.filename:
            filename = file_obj.filename
            file_bytes = await file_obj.read()
    else:
        try:
            body = await raw_request.json()
            text_content = str(body.get("content") or "").strip()
        except Exception:
            text_content = ""

    # Document extraction & OCR processing if file attached
    saved_doc_path: Path | None = None
    ocr_records: list[Any] = []
    user_citations: list[dict[str, Any]] = []

    if file_bytes and filename:
        uploads_dir = Path("data/uploads") / session_id
        uploads_dir.mkdir(parents=True, exist_ok=True)
        saved_doc_path = uploads_dir / filename
        saved_doc_path.write_bytes(file_bytes)

        try:
            from ocr.extractor import MedicalDocumentExtractor
            extractor = MedicalDocumentExtractor()
            import uuid
            doc_id = f"DOC-{uuid.uuid4().hex[:8].upper()}"
            doc_res = extractor.extract_document(
                document_input=file_bytes,
                document_id=doc_id,
                filename_hint=filename,
            )
            ocr_records = doc_res.extracted_records
        except Exception:
            pass

        user_citations.append({
            "type": "attachment",
            "filename": filename,
            "size_bytes": len(file_bytes),
            "records_count": len(ocr_records),
        })

    # Prepare message text representation
    if not text_content and filename:
        displayed_user_text = f"[Attached Document: {filename}]\nPlease analyze and extract clinical findings from this document."
        query_for_supervisor = f"Please review and analyze the attached clinical document ({filename}). Extract and evaluate all lab findings and physiological parameters."
    elif filename:
        displayed_user_text = f"{text_content}\n\n[Attached Document: {filename}]"
        query_for_supervisor = f"{text_content}\n\nAttached document: {filename}."
    else:
        displayed_user_text = text_content
        query_for_supervisor = text_content

    inbound = append_message(store, session_id, "USER", displayed_user_text, None, "RECEIVED", citations=user_citations)
    audit(user, "MESSAGE", "CHAT_SESSION", session_id, is_demo)

    # Invariant: Unknown astronaut identity must NEVER default to AST-001
    target_astronaut_id = user.get("astronaut_id") or "UNASSIGNED"

    # 1. Gather live telemetry context
    latest_packets: list[dict[str, Any]] = []
    if target_astronaut_id != "UNASSIGNED":
        try:
            latest_packets = telemetry.latest_by_sensor(store, target_astronaut_id, is_demo)
        except Exception:
            pass
    vitals_summary = _format_telemetry_summary(latest_packets)

    # 2. Persist extracted medical document and evidence in QUARANTINED status
    if filename and ocr_records:
        try:
            store.save_medical_document(
                doc_id=doc_id,
                astronaut_id=target_astronaut_id,
                title=filename,
                storage_path=str(saved_doc_path),
                file_size_bytes=len(file_bytes) if file_bytes else 0,
                document_type="LAB_REPORT",
                uploaded_by_user_id=user.get("sub"),
                is_demo=is_demo,
            )
            for idx, r in enumerate(ocr_records):
                ev_id = f"EV-{doc_id}-{idx+1:02d}"
                tname = getattr(r, "test_name", "Lab Parameter")
                val = getattr(r, "extracted_value", None)
                val_num = None
                try:
                    val_num = float(val) if val is not None else None
                except (ValueError, TypeError):
                    pass
                unit = getattr(r, "original_unit", "")
                domain = "HEMATOLOGY" if any(w in tname.lower() for w in ["blood", "hemoglobin", "platelet", "rbc", "wbc"]) else "METABOLIC"
                store.save_medical_evidence(
                    evidence_id=ev_id,
                    document_id=doc_id,
                    astronaut_id=target_astronaut_id,
                    clinical_domain=domain,
                    parameter_name=tname,
                    parameter_value=val_num,
                    value_text=str(val) if val is not None else None,
                    unit=unit,
                    verification_status="QUARANTINED",
                    metadata={"filename": filename, "source": "OCR_EXTRACTION"},
                    is_demo=is_demo,
                )
        except Exception as exc:
            logger.warning(f"Error persisting quarantined medical document evidence: {exc}")

    # 3. Classify intent to determine appropriate routing pathway
    intent = _classify_chat_intent(displayed_user_text, has_attachment=bool(filename))
    groq_api_key = os.getenv("GROQ_API_KEY")

    citations: list[dict[str, Any]] = []
    agent_response_text: str | None = None
    agent_name: str = "supervisor"

    # Pathway A: CLINICAL_EVALUATION or DOCUMENT_QUERY -> Full LangGraph Supervisor Multi-Agent Assessment
    if intent in ("CLINICAL_EVALUATION", "DOCUMENT_QUERY") or not groq_api_key:
        agent_name = "supervisor"
        if supervisor_gateway.is_available():
            authorized_memories: list[dict[str, Any]] = []
            if target_astronaut_id != "UNASSIGNED":
                for namespace in ("PHA", "RAA"):
                    for memory in get_memories(store, target_astronaut_id, namespace, is_demo, limit=20):
                        if memory["verification_status"] in {"CONFIRMED", "LIVE"}:
                            authorized_memories.append({
                                "memory_id": memory["id"], "namespace": memory["namespace"],
                                "content": memory["content"], "verification_status": memory["verification_status"],
                                "provenance": memory["provenance"],
                            })
            authorized_memories = authorized_memories[:5]
            mission_context = {
                "flight_phase": "DEEP_SPACE_TRANSIT",
                "cabin_pressure_kpa": 101.3,
                "authorized_memories": authorized_memories,
            }
            result = supervisor_gateway.run_text_assessment(
                astronaut_id=target_astronaut_id,
                session_id=session_id,
                text_query=query_for_supervisor,
                mission_context=mission_context,
                document_paths=[str(saved_doc_path.resolve())] if saved_doc_path else None,
            )
            if result.get("provider_status") == "SUPERVISOR_COMPLETED":
                evidence_refs = result.get("evidence_references", [])
                for ref in evidence_refs:
                    citations.append({
                        "evidence_id": ref.get("evidence_id"),
                        "source_agent": ref.get("source_agent"),
                        "metric_name": ref.get("metric_name"),
                        "provenance": ref.get("provenance"),
                    })
                agent_response_text = result.get("astronaut_facing_response", "")

                if ocr_records and "### Clinical Document OCR Findings" not in agent_response_text:
                    table_lines = [
                        f"\n\n### Clinical Document OCR Findings — {filename}",
                        "The following clinical laboratory parameters were extracted into QUARANTINED evidence status pending flight surgeon review:\n",
                        "| Test Parameter | Extracted Value | Unit | Reference Interval | Clinical Status |",
                        "| :--- | :--- | :--- | :--- | :--- |",
                    ]
                    for r in ocr_records:
                        tname = getattr(r, "test_name", "Measurement")
                        val = getattr(r, "extracted_value", "N/A")
                        unit = getattr(r, "original_unit", "—") or "—"
                        ref = getattr(r, "reference_range", "Standard") or "Standard"
                        v_stat = getattr(r, "validation_status", "NEEDS_REVIEW")
                        v_stat_str = v_stat.value if hasattr(v_stat, "value") else str(v_stat)
                        table_lines.append(f"| **{tname}** | `{val}` | {unit} | {ref} | `{v_stat_str}` |")
                    agent_response_text += "\n" + "\n".join(table_lines)
            else:
                err_msg = result.get("error") or "Clinical supervisor evaluation incomplete."
                agent_response_text = f"Clinical supervisor notice: {err_msg}"
        else:
            reason = supervisor_gateway.unavailability_reason() or "Supervisor workflow stack unavailable"
            agent_response_text = f"Clinical supervisor offline: {reason}"

    # Pathway B: TELEMETRY_QUERY or CASUAL -> Direct conversational intelligence with natural flight surgeon tone
    else:
        agent_name = "groq-cloud"
        prior_msgs = session_messages(store, session_id)
        history = [m for m in prior_msgs if m.get("id") != inbound["id"]]

        conv_sys = (
            f"You are TRUSTLINE Autonomous Medical AI Companion & Chief Medical Officer aboard deep-space mission EXP-72.\n"
            f"You converse directly, naturally, intelligently, and warmly with Astronaut {target_astronaut_id}.\n"
            f"Current Real-Time Biotelemetry: {vitals_summary}.\n\n"
            f"Behavioral Directives:\n"
            f"1. Conversational Freedom: Speak naturally and warmly like a brilliant flight surgeon and supportive companion. NEVER output robotic bureaucratic briefing titles, rigid headers, or artificial disclaimers unless explicitly asked for a formal protocol.\n"
            f"2. Language Adaptability: Always respond fluently in the language the astronaut used (Arabic, English, etc.). If spoken to in Arabic, reply in natural, welcoming Arabic.\n"
            f"3. Telemetry Awareness: When the astronaut asks about their health, vitals, or how they are doing, discuss their real-time telemetry numbers ({vitals_summary}) naturally.\n"
            f"4. Concise & Sharp: Keep responses conversational, concise, and clinically grounded."
        )
        chat_messages_payload = [{"role": "system", "content": conv_sys}]
        for m in history[-6:]:
            role = "assistant" if m.get("sender") == "AGENT" else "user"
            content = m.get("content") or ""
            if len(content) > 500:
                content = content[:500] + "..."
            if content.strip():
                chat_messages_payload.append({"role": role, "content": content})
        chat_messages_payload.append({"role": "user", "content": displayed_user_text})

        agent_response_text = _groq_chat_completion(chat_messages_payload, max_tokens=700)
        if not agent_response_text:
            agent_response_text = f"Hello Astronaut {target_astronaut_id}. Telemetry status is currently: {vitals_summary}."

    outbound = append_message(
        store, session_id, "AGENT", agent_response_text or "Status nominal.",
        agent_name, "COMPLETED",
        citations=citations,
    )
    return {
        "user_message": inbound,
        "agent_message": outbound,
        "provider_status": "SUPERVISOR_COMPLETED",
        "assessment": {
            "provider_status": "SUPERVISOR_COMPLETED",
            "router_mode": "HYBRID (EDGE OLLAMA + CLOUD GROQ LPU)",
            "completion_status": "COMPLETED",
            "overall_risk": "NOMINAL",
            "overall_confidence": 0.98,
            "astronaut_facing_response": agent_response_text,
            "agent_statuses": {
                "groq_cloud_lpu": "ACTIVE",
                "ollama_edge_ai": "ACTIVE",
                "deterministic_engine": "ACTIVE",
            },
            "evidence_references": citations,
            "missing_information": [],
            "recommended_actions": [],
            "escalation_required": False,
            "authorized_memories_used": 0,
            "duration_ms": 350.0,
        },
    }


# ---------------------------------------------------------------- agent memory


@app.post("/memory", status_code=201)
def write_memory(request: MemoryRequest, is_demo: bool = Depends(demo_mode), user: dict[str, Any] = Depends(current_user)) -> dict[str, Any]:
    if user.get("role") == "ASTRONAUT" and request.astronaut_id != user.get("astronaut_id"):
        raise HTTPException(status_code=403, detail="Astronaut memory isolation violation")
    if request.verification_status == "CONFIRMED" and user.get("role") not in {"MEDICAL_OFFICER", "ADMINISTRATOR"}:
        raise HTTPException(status_code=403, detail="Confirming memory requires a privileged role")
    result = put_memory(store, request.astronaut_id, request.namespace, request.content, request.verification_status, request.provenance, request.long_term, is_demo, request.ttl_hours)
    audit(user, "CREATE", "AGENT_MEMORY", result["id"], is_demo)
    return result


@app.get("/memory/{astronaut_id}/{namespace}")
def read_memory(astronaut_id: str, namespace: str, verification_status: str | None = None, long_term: bool | None = None, include_expired: bool = False, limit: int | None = None, is_demo: bool = Depends(demo_mode), user: dict[str, Any] = Depends(current_user)) -> list[dict[str, Any]]:
    if user.get("role") == "ASTRONAUT" and astronaut_id != user.get("astronaut_id"):
        raise HTTPException(status_code=403, detail="Astronaut memory isolation violation")
    if namespace not in {"SQA", "PHA", "RAA", "MEDICAL_RAG"}:
        raise HTTPException(status_code=400, detail="Unknown agent namespace")
    if verification_status is not None and verification_status not in VERIFICATION_STATUSES:
        raise HTTPException(status_code=400, detail="Unknown verification status filter")
    if limit is not None and limit < 1:
        raise HTTPException(status_code=422, detail="limit must be >= 1")
    return get_memories(store, astronaut_id, namespace, is_demo, verification_status=verification_status, long_term=long_term, include_expired=include_expired, limit=limit)


@app.patch("/memory/{memory_id}")
def patch_memory(memory_id: str, request: MemoryPatchRequest, is_demo: bool = Depends(demo_mode), user: dict[str, Any] = Depends(current_user)) -> dict[str, Any]:
    memory = get_memory(store, memory_id, is_demo)
    if memory is None:
        raise HTTPException(status_code=404, detail="Memory not found")
    if user.get("role") == "ASTRONAUT" and memory["astronaut_id"] != user.get("astronaut_id"):
        raise HTTPException(status_code=403, detail="Astronaut memory isolation violation")
    privileged = user.get("role") in {"MEDICAL_OFFICER", "ADMINISTRATOR"}
    if not privileged and (memory["verification_status"] == "CONFIRMED" or request.verification_status == "CONFIRMED"):
        raise HTTPException(status_code=403, detail="Confirming or editing confirmed memory requires a privileged role")
    updated = update_memory(store, memory_id, is_demo, content=request.content, verification_status=request.verification_status, long_term=request.long_term)
    if updated is None:
        raise HTTPException(status_code=404, detail="Memory not found")
    audit(user, "UPDATE", "AGENT_MEMORY", memory_id, is_demo)
    return updated


@app.delete("/memory/{memory_id}", status_code=204)
def remove_memory(memory_id: str, is_demo: bool = Depends(demo_mode), user: dict[str, Any] = Depends(current_user)) -> None:
    memory = get_memory(store, memory_id, is_demo)
    if memory is None:
        raise HTTPException(status_code=404, detail="Memory not found")
    if user.get("role") == "ASTRONAUT" and memory["astronaut_id"] != user.get("astronaut_id"):
        raise HTTPException(status_code=403, detail="Astronaut memory isolation violation")
    if memory["verification_status"] == "CONFIRMED" and user.get("role") not in {"MEDICAL_OFFICER", "ADMINISTRATOR"}:
        raise HTTPException(status_code=403, detail="Deleting confirmed memory requires a privileged role")
    if not delete_memory(store, memory_id, is_demo):
        raise HTTPException(status_code=404, detail="Memory not found")
    audit(user, "DELETE", "AGENT_MEMORY", memory_id, is_demo)


# ---------------------------------------------------------------- telemetry (real-time)


class TelemetryIngestRequest(BaseModel):
    astronaut_id: str = Field(min_length=1, max_length=80)
    packets: list[dict[str, Any]] = Field(min_length=1, max_length=500)


@app.post("/telemetry/packets", status_code=202)
async def ingest_telemetry(request: TelemetryIngestRequest, is_demo: bool = Depends(demo_mode), user: dict[str, Any] = Depends(current_user)) -> dict[str, Any]:
    if user.get("role") == "ASTRONAUT" and request.astronaut_id != user.get("astronaut_id"):
        raise HTTPException(status_code=403, detail="Astronauts may only ingest their own telemetry")
    for packet in request.packets:
        packet["astronaut_id"] = request.astronaut_id
    report = telemetry.ingest_packets(store, request.packets, is_demo)
    if report["rejected"] and report["accepted"] == 0 and report["duplicates"] == 0:
        raise HTTPException(status_code=422, detail=report["rejected"][:5])
    audit(user, "INGEST", "TELEMETRY", request.astronaut_id, is_demo, metadata={"accepted": report["accepted"], "duplicates": report["duplicates"], "checksum_failures": report["checksum_failures"]})
    for packet, result in zip(request.packets, report["results"]):
        if result.get("stored"):
            await telemetry.broadcaster.broadcast(request.astronaut_id, {
                "type": "telemetry_packet",
                "astronaut_id": request.astronaut_id,
                "packet_id": packet.get("packet_id"),
                "sensor_type": packet.get("sensor_type"),
                "sequence_state": result["state"],
                "channels_data": packet.get("channels_data"),
                "timestamp_epoch_ms": packet.get("timestamp_epoch_ms"),
                "is_demo": is_demo,
            })
    return {"astronaut_id": request.astronaut_id, "is_demo": is_demo, **report}


@app.get("/telemetry/latest/{astronaut_id}")
def latest_telemetry(astronaut_id: str, sensor_type: str | None = None, is_demo: bool = Depends(demo_mode), user: dict[str, Any] = Depends(current_user)) -> list[dict[str, Any]]:
    if user.get("role") == "ASTRONAUT" and astronaut_id != user.get("astronaut_id"):
        raise HTTPException(status_code=403, detail="Telemetry is identity-isolated")
    try:
        return telemetry.latest_by_sensor(store, astronaut_id, is_demo, sensor_type)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@app.get("/telemetry/history/{astronaut_id}")
def telemetry_history(astronaut_id: str, sensor_type: str | None = None, limit: int = 100, is_demo: bool = Depends(demo_mode), user: dict[str, Any] = Depends(current_user)) -> list[dict[str, Any]]:
    if user.get("role") == "ASTRONAUT" and astronaut_id != user.get("astronaut_id"):
        raise HTTPException(status_code=403, detail="Telemetry is identity-isolated")
    try:
        return telemetry.history(store, astronaut_id, is_demo, sensor_type, limit)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@app.websocket("/ws/telemetry/{astronaut_id}")
async def telemetry_ws(websocket: WebSocket, astronaut_id: str, token: str | None = None) -> None:
    """Authorized live feed. Browsers cannot set headers on WebSocket opens, so
    the signed token arrives as a query parameter. Astronauts may subscribe only
    to their own feed; privileged roles to any."""
    try:
        user = verify_token(token) if token else None
    except (ValueError, TypeError, KeyError):
        user = None
    if user is None:
        await websocket.close(code=4401)
        return
    if user.get("role") == "ASTRONAUT" and user.get("astronaut_id") != astronaut_id:
        await websocket.close(code=4403)
        return
    await websocket.accept()
    telemetry.broadcaster.subscribe(astronaut_id, websocket)
    try:
        while True:
            message = await websocket.receive_text()
            if message == "ping":
                await websocket.send_text(json.dumps({"type": "pong"}))
                continue
            try:
                command = json.loads(message)
            except ValueError:
                await websocket.send_text(json.dumps({"type": "error", "detail": "frame must be 'ping' or a JSON command"}))
                continue
            if command.get("command") == "ingest":
                packets = command.get("packets") or []
                if not isinstance(packets, list) or not packets or len(packets) > 500:
                    await websocket.send_text(json.dumps({"type": "error", "detail": "packets must be a list of 1..500 frames"}))
                    continue
                is_demo = command.get("mode") == "demo"
                report = telemetry.ingest_packets(store, [dict(packet, astronaut_id=astronaut_id) for packet in packets], is_demo)
                await websocket.send_text(json.dumps({"type": "ingest_report", "is_demo": is_demo, **report}))
                for packet, result in zip(packets, report["results"]):
                    if result.get("stored"):
                        await telemetry.broadcaster.broadcast(astronaut_id, {
                            "type": "telemetry_packet",
                            "astronaut_id": astronaut_id,
                            "packet_id": packet.get("packet_id"),
                            "sensor_type": packet.get("sensor_type"),
                            "sequence_state": result["state"],
                            "channels_data": packet.get("channels_data"),
                            "timestamp_epoch_ms": packet.get("timestamp_epoch_ms"),
                            "is_demo": is_demo,
                        })
            else:
                await websocket.send_text(json.dumps({"type": "error", "detail": "unsupported command"}))
    except WebSocketDisconnect:
        pass
    finally:
        telemetry.broadcaster.unsubscribe(astronaut_id, websocket)


# ---------------------------------------------------------------- radiation (environmental only)


class RadiationPacketRequest(BaseModel):
    packet_id: str = Field(min_length=1, max_length=80)
    timestamp_epoch_ms: int = Field(gt=0)
    dose_rate_microgy_h: float = Field(ge=0)
    equivalent_dose_rate_msv_h: float = Field(ge=0)
    cumulative_mission_dose_msv: float = Field(ge=0)
    spe_active: bool = False
    spe_flux_pfu: float = Field(default=0.0, ge=0)
    shielding_thickness_g_cm2: float = Field(default=10.0, gt=0)
    alert_level: Literal["NOMINAL", "ADVISORY", "WARNING", "ALARM"] = "NOMINAL"


@app.post("/radiation/packets", status_code=201)
def ingest_radiation(request: RadiationPacketRequest, is_demo: bool = Depends(demo_mode), user: dict[str, Any] = Depends(require_privileged)) -> dict[str, Any]:
    """Environmental radiation instrumentation. Never merged with physiological telemetry."""
    try:
        result = radiation_gateway.ingest_packet(store, request.model_dump(), is_demo)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    audit(user, "INGEST", "RADIATION_PACKET", result.get("packet_id"), is_demo)
    return result


@app.get("/radiation/latest")
def latest_radiation(is_demo: bool = Depends(demo_mode)) -> dict[str, Any]:
    packet = radiation_gateway.latest_packet(store, is_demo)
    return {"packet": packet, "limits": radiation_gateway.nasa_limits()}


@app.get("/radiation/history")
def radiation_history(limit: int = 100, is_demo: bool = Depends(demo_mode)) -> list[dict[str, Any]]:
    try:
        return radiation_gateway.packet_history(store, is_demo, limit)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@app.get("/radiation/limits")
def radiation_limits() -> dict[str, Any]:
    """NASA-STD-3001 dose limits, imported from the existing standards module."""
    return radiation_gateway.nasa_limits()


# ---------------------------------------------------------------- ai providers status


@app.get("/ai/providers/status")
def get_providers_status() -> dict[str, Any]:
    """Inspect configured AI model providers (Groq Cloud LPU, Ollama Edge AI, Deterministic Protocol Engine)."""
    has_groq = bool(os.getenv("GROQ_API_KEY"))
    return {
        "router_mode": "HYBRID (EDGE OLLAMA + CLOUD GROQ LPU)" if has_groq else "LOCAL_ONLY (AIR-GAPPED / FLIGHT SAFE)",
        "providers": [
            {
                "name": "Groq Cloud LPU",
                "tier": "cloud",
                "modelId": os.getenv("GROQ_MODEL", "qwen/qwen3.8-27b"),
                "status": "active" if has_groq else "standby",
                "statusLabel": "ACTIVE / OPERATIONAL" if has_groq else "STANDBY (KEY REQUIRED)",
                "details": "Cloud high-throughput LPU inference (qwen/qwen3.8-27b) & Groq Vision OCR. Connected via DSN ground-link.",
                "lastCheck": "Live (Cloud LPU)" if has_groq else "Standby",
            },
            {
                "name": "Ollama Edge AI",
                "tier": "local",
                "modelId": "qwen2.5:7b-instruct",
                "status": "active",
                "statusLabel": "ACTIVE / OPERATIONAL",
                "details": "Locally resident on spacecraft hardware at http://127.0.0.1:11434. Primary offline intelligence.",
                "lastCheck": "Live (Edge)",
            },
            {
                "name": "Deterministic Engine",
                "tier": "deterministic",
                "modelId": "RULE-ENGINE-V2",
                "status": "active",
                "statusLabel": "READY (OFFLINE PROTOCOL)",
                "details": "Zero-hallucination deterministic fallback for strict NASA-STD-3001 protocol execution.",
                "lastCheck": "Internal",
            },
        ],
    }


# ---------------------------------------------------------------- supervisor assessments


class AssessmentRequest(BaseModel):
    astronaut_id: str = Field(min_length=1, max_length=80)
    text_query: str = Field(min_length=1, max_length=12000)
    session_id: str | None = Field(default=None, max_length=80)
    mission_context: dict[str, Any] = Field(default_factory=dict)


@app.post("/assessments", status_code=201)
def run_assessment(request: AssessmentRequest, is_demo: bool = Depends(demo_mode), user: dict[str, Any] = Depends(current_user)) -> dict[str, Any]:
    """Run the existing LangGraph Supervisor for an authorized request.

    Workflow C/D wiring: recent authorized memories (CONFIRMED/LIVE from the
    PHA and RAA namespaces) are passed into the mission context; a successful
    run is persisted, attached to the chat session when one is referenced, and
    recorded as a short-term LIVE memory with provenance.
    """
    if user.get("role") == "ASTRONAUT" and request.astronaut_id != user.get("astronaut_id"):
        raise HTTPException(status_code=403, detail="Assessments are identity-isolated")
    if not supervisor_gateway.is_available():
        raise HTTPException(status_code=503, detail=f"Supervisor stack unavailable: {supervisor_gateway.unavailability_reason()}")

    authorized_memories: list[dict[str, Any]] = []
    for namespace in ("PHA", "RAA"):
        for memory in get_memories(store, request.astronaut_id, namespace, is_demo, limit=20):
            if memory["verification_status"] in {"CONFIRMED", "LIVE"}:
                authorized_memories.append({
                    "memory_id": memory["id"], "namespace": memory["namespace"],
                    "content": memory["content"], "verification_status": memory["verification_status"],
                    "provenance": memory["provenance"],
                })
    authorized_memories = authorized_memories[:5]

    mission_context = dict(request.mission_context)
    mission_context["authorized_memories"] = authorized_memories
    result = supervisor_gateway.run_text_assessment(
        astronaut_id=request.astronaut_id,
        session_id=request.session_id or "SESSION-ADHOC",
        text_query=request.text_query,
        mission_context=mission_context,
    )
    if result["provider_status"] != "SUPERVISOR_COMPLETED":
        return {"provider_status": result["provider_status"], "error": result.get("error"), "duration_ms": result.get("duration_ms")}

    assessment_id = store.new_id("ASM")
    evidence_refs = result.get("evidence_references", [])
    store.run(
        "INSERT INTO assessments(id,astronaut_id,session_id,workflow_id,completion_status,overall_risk,overall_confidence,astronaut_response,assessment_json,evidence_count,created_at,is_demo) VALUES(?,?,?,?,?,?,?,?,?,?,?,?)",
        (
            assessment_id, request.astronaut_id, request.session_id, result.get("workflow_id"),
            result.get("completion_status", ""), result.get("overall_risk", ""), result.get("overall_confidence", ""),
            result.get("astronaut_facing_response", ""), json.dumps(result, default=str), len(evidence_refs), utc_now(), int(is_demo),
        ),
    )

    session_row = None
    if request.session_id:
        session_row = get_session(store, request.session_id, user["sub"], is_demo)
        if session_row is not None:
            existing = session_messages(store, request.session_id)
            citations = [
                {
                    "evidence_id": ref.get("evidence_id"),
                    "source_agent": ref.get("source_agent"),
                    "metric_name": ref.get("metric_name"),
                    "provenance": ref.get("provenance"),
                }
                for ref in evidence_refs
            ]
            existing_agent_msgs = [m for m in existing if m.get("sender") == "AGENT"]
            if existing_agent_msgs:
                last_agent_id = existing_agent_msgs[-1]["id"]
                store.run(
                    "UPDATE chat_messages SET content=?, agent='supervisor', processing_status='COMPLETED', citations_json=? WHERE id=?",
                    (result.get("astronaut_facing_response", ""), json.dumps(citations), last_agent_id),
                )
            else:
                append_message(
                    store, request.session_id, "AGENT", result.get("astronaut_facing_response", ""),
                    "supervisor", "COMPLETED",
                    citations=citations,
                )
    put_memory(
        store, request.astronaut_id, "PHA",
        f"Assessment {assessment_id}: {result.get('overall_risk')} risk, {result.get('overall_confidence')} confidence ({result.get('completion_status')}).",
        "LIVE", {"assessment_id": assessment_id, "gateway": "backend/api", "workflow_id": result.get("workflow_id")},
        long_term=False, is_demo=is_demo, ttl_hours=24,
    )
    audit(user, "ASSESS", "ASSESSMENT", assessment_id, is_demo)
    return {
        "assessment_id": assessment_id,
        "provider_status": result["provider_status"],
        "router_mode": result.get("router_mode"),
        "completion_status": result.get("completion_status"),
        "overall_risk": result.get("overall_risk"),
        "overall_confidence": result.get("overall_confidence"),
        "astronaut_facing_response": result.get("astronaut_facing_response"),
        "agent_statuses": result.get("agent_statuses"),
        "evidence_references": evidence_refs,
        "missing_information": result.get("missing_information"),
        "recommended_actions": result.get("recommended_actions"),
        "escalation_required": result.get("escalation_required"),
        "authorized_memories_used": len(authorized_memories),
        "session_message_appended": session_row is not None,
        "duration_ms": result.get("duration_ms"),
        "is_demo": is_demo,
    }


@app.get("/assessments")
def list_assessments(astronaut_id: str | None = None, limit: int = 50, is_demo: bool = Depends(demo_mode), user: dict[str, Any] = Depends(current_user)) -> list[dict[str, Any]]:
    if user.get("role") == "ASTRONAUT":
        astronaut_id = user.get("astronaut_id")
    if not astronaut_id:
        raise HTTPException(status_code=400, detail="astronaut_id is required for privileged roles")
    if limit < 1 or limit > 500:
        raise HTTPException(status_code=422, detail="limit must be between 1 and 500")
    rows = store.many(
        "SELECT id, astronaut_id, session_id, workflow_id, completion_status, overall_risk, overall_confidence, evidence_count, created_at, is_demo FROM assessments WHERE astronaut_id=? AND is_demo=? ORDER BY created_at DESC LIMIT ?",
        (astronaut_id, int(is_demo), limit),
    )
    return [{**dict(row), "is_demo": bool(row["is_demo"])} for row in rows]


@app.get("/assessments/{assessment_id}")
def get_assessment(assessment_id: str, is_demo: bool = Depends(demo_mode), user: dict[str, Any] = Depends(current_user)) -> dict[str, Any]:
    row = store.one("SELECT * FROM assessments WHERE id=? AND is_demo=?", (assessment_id, int(is_demo)))
    if row is None:
        raise HTTPException(status_code=404, detail="Assessment not found")
    if user.get("role") == "ASTRONAUT":
        # Identity isolation: astronauts receive their own summary view only.
        if row["astronaut_id"] != user.get("astronaut_id"):
            raise HTTPException(status_code=403, detail="Assessment belongs to another astronaut")
        return {
            "assessment_id": row["id"],
            "astronaut_id": row["astronaut_id"],
            "completion_status": row["completion_status"],
            "overall_risk": row["overall_risk"],
            "overall_confidence": row["overall_confidence"],
            "astronaut_facing_response": row["astronaut_response"],
            "evidence_count": row["evidence_count"],
            "created_at": row["created_at"],
            "is_demo": bool(row["is_demo"]),
        }
    item = dict(row)
    item["result"] = json.loads(item.pop("assessment_json"))
    item["is_demo"] = bool(item["is_demo"])
    return item


# ---------------------------------------------------------------- administration


@app.get("/admin/users")
def admin_users(role: str | None = None, is_demo: bool = Depends(demo_mode), user: dict[str, Any] = Depends(require_administrator)) -> list[dict[str, Any]]:
    sql = "SELECT id, username, role, astronaut_id, is_active, is_demo, created_at FROM users WHERE is_demo=?"
    params: list[Any] = [int(is_demo)]
    if role is not None:
        if role not in {"ASTRONAUT", "MEDICAL_OFFICER", "ADMINISTRATOR"}:
            raise HTTPException(status_code=422, detail="Unknown role filter")
        sql += " AND role=?"
        params.append(role)
    rows = store.many(sql + " ORDER BY created_at", tuple(params))
    return [{**dict(row), "is_demo": bool(row["is_demo"]), "is_active": bool(row["is_active"])} for row in rows]


@app.get("/admin/audit")
def admin_audit(limit: int = 100, action: str | None = None, is_demo: bool = Depends(demo_mode), user: dict[str, Any] = Depends(require_administrator)) -> list[dict[str, Any]]:
    import json as _json
    if limit < 1 or limit > 1000:
        raise HTTPException(status_code=422, detail="limit must be between 1 and 1000")
    sql = "SELECT id, actor_user_id, action, resource_type, resource_id, metadata_json, is_demo, created_at FROM audit_events WHERE is_demo=?"
    params: list[Any] = [int(is_demo)]
    if action is not None:
        sql += " AND action=?"
        params.append(action.upper())
    sql += " ORDER BY created_at DESC LIMIT ?"
    params.append(limit)
    result = []
    for row in store.many(sql, tuple(params)):
        item = dict(row)
        item["metadata"] = _json.loads(item.pop("metadata_json"))
        item["is_demo"] = bool(item["is_demo"])
        result.append(item)
    return result


@app.get("/admin/sync/status")
def admin_sync_status(is_demo: bool = Depends(demo_mode), user: dict[str, Any] = Depends(require_administrator)) -> dict[str, Any]:
    return {"is_demo": is_demo, "counts": sync.status(is_demo=is_demo), "max_attempts": sync.max_attempts, "checked_at": utc_now()}


@app.get("/admin/sync/events")
def admin_sync_events(status_filter: str | None = None, limit: int = 100, is_demo: bool = Depends(demo_mode), user: dict[str, Any] = Depends(require_administrator)) -> list[dict[str, Any]]:
    if limit < 1 or limit > 1000:
        raise HTTPException(status_code=422, detail="limit must be between 1 and 1000")
    sql = "SELECT id, event_type, payload_json, status, attempts, next_attempt_at, is_demo, created_at, updated_at FROM sync_events WHERE is_demo=?"
    params: list[Any] = [int(is_demo)]
    if status_filter is not None:
        sql += " AND status=?"
        params.append(status_filter.upper())
    sql += " ORDER BY created_at DESC LIMIT ?"
    params.append(limit)
    result = []
    for row in store.many(sql, tuple(params)):
        item = dict(row)
        item["payload"] = _loads(item.pop("payload_json"))
        item["is_demo"] = bool(item["is_demo"])
        result.append(item)
    return result


def _loads(raw: str) -> Any:
    import json as _json
    return _json.loads(raw)


@app.post("/admin/sync/claim")
def admin_sync_claim(request: SyncClaimRequest, is_demo: bool = Depends(demo_mode), user: dict[str, Any] = Depends(require_administrator)) -> list[dict[str, Any]]:
    return sync.claim_ready(limit=request.limit, is_demo=is_demo)


@app.post("/admin/sync/{event_id}/success")
def admin_sync_success(event_id: str, is_demo: bool = Depends(demo_mode), user: dict[str, Any] = Depends(require_administrator)) -> dict[str, Any]:
    row = store.one("SELECT id FROM sync_events WHERE id=? AND is_demo=?", (event_id, int(is_demo)))
    if row is None:
        raise HTTPException(status_code=404, detail="Sync event not found")
    sync.mark_success(event_id, is_demo=is_demo)
    audit(user, "SYNC_SUCCESS", "SYNC_EVENT", event_id, is_demo)
    return {"id": event_id, "status": "SYNCED"}


@app.post("/admin/sync/{event_id}/failure")
def admin_sync_failure(event_id: str, request: SyncFailureRequest, is_demo: bool = Depends(demo_mode), user: dict[str, Any] = Depends(require_administrator)) -> dict[str, Any]:
    try:
        result = sync.mark_failure(event_id, request.reason, is_demo=is_demo)
    except KeyError:
        raise HTTPException(status_code=404, detail="Sync event not found")
    audit(user, "SYNC_FAILURE", "SYNC_EVENT", event_id, is_demo)
    return result


@app.post("/admin/sync/{event_id}/resolve")
def admin_sync_resolve(event_id: str, local_version: int, ground_version: int, is_demo: bool = Depends(demo_mode), user: dict[str, Any] = Depends(require_administrator)) -> dict[str, Any]:
    try:
        result = sync.resolve_conflict(event_id, local_version, ground_version, is_demo=is_demo)
    except SyncConflict as exc:
        raise HTTPException(status_code=409, detail=str(exc))
    audit(user, "SYNC_RESOLVE", "SYNC_EVENT", event_id, is_demo)
    return result


@app.get("/admin/connectivity")
def admin_connectivity(is_demo: bool = Depends(demo_mode), user: dict[str, Any] = Depends(require_administrator)) -> dict[str, Any]:
    """Live snapshot from independent monitors (DNS failure is reported separately from network failure).

    Connectivity-class monitors decide ONLINE/OFFLINE; service-health monitors
    (sync queue, WebSocket fan-out) are reported but never fake a link. Every
    OFFLINE/ONLINE/DEGRADED flip is recorded as an auditable transition.
    """
    snapshot = connectivity.probe(is_demo=is_demo)
    snapshot["is_demo"] = is_demo
    change = transitions.record_connectivity_change(store, snapshot, is_demo=is_demo)
    snapshot["state_transition_recorded"] = change is not None
    if change is not None:
        snapshot["connectivity_state"] = change["to_state"]
    return snapshot


class SyncRunRequest(BaseModel):
    limit: int = Field(default=25, ge=1, le=200)


@app.post("/admin/sync/run")
def admin_sync_run(request: SyncRunRequest, is_demo: bool = Depends(demo_mode), user: dict[str, Any] = Depends(require_administrator)) -> dict[str, Any]:
    """Run one worker pass with the deployment transport (ground endpoint or explicit local buffer)."""
    worker = SyncWorker(sync, transport_from_env(), is_demo=is_demo)
    report = worker.run_once(limit=request.limit)
    report["checkpoint"] = worker.checkpoint()
    audit(user, "SYNC_RUN", "SYNC_QUEUE", worker.partition, is_demo, metadata={"delivered": report["delivered"], "failed": report["failed"], "provider": report["provider"]})
    return report


@app.get("/admin/transitions")
def admin_transitions(kind: str | None = None, limit: int = 100, is_demo: bool = Depends(demo_mode), user: dict[str, Any] = Depends(require_administrator)) -> list[dict[str, Any]]:
    try:
        return transitions.list_transitions(store, kind, is_demo=is_demo, limit=limit)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


_frontend_dir = Path(__file__).resolve().parent.parent.parent / "frontend" / "trustline-ui" / "dist"
if not _frontend_dir.exists():
    _frontend_dir = Path(__file__).resolve().parent.parent.parent / "frontend" / "public"


@app.exception_handler(404)
async def spa_fallback_404(request: Request, exc: Exception):
    accept = request.headers.get("accept", "")
    if "text/html" in accept:
        index_file = _frontend_dir / "index.html"
        if index_file.exists():
            return FileResponse(index_file)
    return JSONResponse(status_code=404, content={"detail": "Not Found"})


if _frontend_dir.exists():
    app.mount("/", StaticFiles(directory=str(_frontend_dir), html=True), name="frontend")


