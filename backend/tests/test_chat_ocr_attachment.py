"""Test chatbot document attachment and OCR extraction integration with LangGraph supervisor."""
import io
from fastapi.testclient import TestClient
import fitz

def _setup(monkeypatch, tmp_path):
    monkeypatch.setenv("TRUSTLINE_DB_PATH", str(tmp_path / "chat_ocr.db"))
    from backend.api import app as module
    module.store.configure(str(tmp_path / "chat_ocr.db"))
    client = TestClient(module.app)
    assert client.post("/auth/register", json={"username": "astro_ocr", "password": "a-very-strong-password", "role": "ASTRONAUT", "astronaut_id": "AST-001"}).status_code == 201
    token = client.post("/auth/login", json={"username": "astro_ocr", "password": "a-very-strong-password"}).json()["access_token"]
    return module, client, {"Authorization": f"Bearer {token}"}

def make_sample_pdf() -> bytes:
    doc = fitz.open()
    page = doc.new_page(width=595, height=842)
    page.insert_text((50, 72), "CLINICAL LABORATORY BLOOD PANEL — AST-001", fontsize=14)
    page.insert_text(
        (50, 120),
        "Hemoglobin: 14.8 g/dL (Reference: 13.5-17.5)\n"
        "Platelets: 240 10^3/uL (Reference: 150-450)\n"
        "Serum Glucose: 92 mg/dL (Reference: 70-99)\n"
        "Blood Urea Nitrogen: 16 mg/dL (Reference: 7-20)\n",
        fontsize=11
    )
    pdf_bytes = doc.tobytes()
    doc.close()
    return pdf_bytes

def test_chat_message_with_pdf_ocr(monkeypatch, tmp_path):
    module, client, headers = _setup(monkeypatch, tmp_path)

    # 1. Create a chat session
    res_session = client.post("/chat/sessions", json={"title": "Lab Review"}, headers=headers)
    assert res_session.status_code == 201
    session_id = res_session.json()["id"]

    # 2. Upload PDF attachment
    pdf_bytes = make_sample_pdf()
    files = {"file": ("blood_panel.pdf", pdf_bytes, "application/pdf")}
    data = {"content": "Please review my latest spaceflight blood panel results."}

    res_msg = client.post(
        f"/chat/sessions/{session_id}/messages",
        headers=headers,
        data=data,
        files=files,
    )
    assert res_msg.status_code == 201, res_msg.text
    payload = res_msg.json()

    assert payload["provider_status"] == "SUPERVISOR_COMPLETED"
    assert "user_message" in payload
    assert "agent_message" in payload

    user_msg = payload["user_message"]
    assert "[Attached Document: blood_panel.pdf]" in user_msg["content"]
    assert len(user_msg.get("citations", [])) > 0
    assert user_msg["citations"][0]["filename"] == "blood_panel.pdf"

    agent_msg = payload["agent_message"]
    assert "TRUSTLINE Mission Health Briefing" in agent_msg["content"]
    assert len(agent_msg.get("citations", [])) > 0
    print("\n--- AGENT BRIEFING WITH OCR FINDINGS ---")
    print(agent_msg["content"])
