"""Chat session lifecycle: rename, archive, delete, search, enrichment, isolation."""
from fastapi.testclient import TestClient


def _setup(monkeypatch, tmp_path):
    monkeypatch.setenv("TRUSTLINE_DB_PATH", str(tmp_path / "chat.db"))
    from backend.api import app as module
    module.store.configure(str(tmp_path / "chat.db"))
    client = TestClient(module.app)
    assert client.post("/auth/register", json={"username": "astro1", "password": "a-very-strong-password", "role": "ASTRONAUT", "astronaut_id": "AST-001"}).status_code == 201
    assert client.post("/auth/register", json={"username": "astro2", "password": "a-very-strong-password", "role": "ASTRONAUT", "astronaut_id": "AST-002"}).status_code == 201
    token = client.post("/auth/login", json={"username": "astro1", "password": "a-very-strong-password"}).json()["access_token"]
    other = client.post("/auth/login", json={"username": "astro2", "password": "a-very-strong-password"}).json()["access_token"]
    return module, client, {"Authorization": f"Bearer {token}"}, {"Authorization": f"Bearer {other}"}


def test_session_is_astronaut_bound_and_lists_enrichment(monkeypatch, tmp_path):
    module, client, headers, other = _setup(monkeypatch, tmp_path)
    session = client.post("/chat/sessions", headers=headers, json={"title": "Mission check-in"}).json()
    assert session["astronaut_id"] == "AST-001"
    client.post(f"/chat/sessions/{session['id']}/messages", headers=headers, json={"content": "feeling lightheaded after EVA"})
    listing = client.get("/chat/sessions", headers=headers).json()
    target = next(s for s in listing if s["id"] == session["id"])
    assert target["message_count"] == 2  # user message + supervisor agent response
    assert len(target["latest_preview"]) > 0  # real supervisor response preview
    assert target["status"] == "ACTIVE"


def test_rename_archive_and_search(monkeypatch, tmp_path):
    module, client, headers, other = _setup(monkeypatch, tmp_path)
    session = client.post("/chat/sessions", headers=headers, json={"title": "EVA debrief"}).json()
    client.post("/chat/sessions", headers=headers, json={"title": "Nutrition notes"}).json()
    # rename
    renamed = client.patch(f"/chat/sessions/{session['id']}", headers=headers, json={"title": "EVA debrief (day 2)"})
    assert renamed.status_code == 200 and renamed.json()["title"] == "EVA debrief (day 2)"
    # archive
    archived = client.patch(f"/chat/sessions/{session['id']}", headers=headers, json={"status": "ARCHIVED"})
    assert archived.status_code == 200 and archived.json()["status"] == "ARCHIVED"
    active = client.get("/chat/sessions", headers=headers).json()
    assert all(s["id"] != session["id"] for s in active)  # archived excluded by default
    archived_list = client.get("/chat/sessions", params={"session_status": "ARCHIVED"}, headers=headers).json()
    assert [s["id"] for s in archived_list] == [session["id"]]
    # search
    found = client.get("/chat/sessions", params={"q": "nutrition"}, headers=headers).json()
    assert len(found) == 1 and found[0]["title"] == "Nutrition notes"
    # unarchive
    unarchived = client.patch(f"/chat/sessions/{session['id']}", headers=headers, json={"status": "ACTIVE"})
    assert unarchived.json()["status"] == "ACTIVE"


def test_delete_removes_session_and_messages(monkeypatch, tmp_path):
    module, client, headers, other = _setup(monkeypatch, tmp_path)
    session = client.post("/chat/sessions", headers=headers, json={"title": "to delete"}).json()
    client.post(f"/chat/sessions/{session['id']}/messages", headers=headers, json={"content": "temporary"})
    assert client.delete(f"/chat/sessions/{session['id']}", headers=headers).status_code == 204
    assert client.get(f"/chat/sessions/{session['id']}/messages", headers=headers).status_code == 404
    assert client.get("/chat/sessions", headers=headers).json() == []
    assert client.delete(f"/chat/sessions/{session['id']}", headers=headers).status_code == 404


def test_ownership_is_enforced_for_management_actions(monkeypatch, tmp_path):
    module, client, headers, other = _setup(monkeypatch, tmp_path)
    session = client.post("/chat/sessions", headers=headers, json={"title": "private"}).json()
    assert client.patch(f"/chat/sessions/{session['id']}", headers=other, json={"title": "hijack"}).status_code == 404
    assert client.delete(f"/chat/sessions/{session['id']}", headers=other).status_code == 404
    assert client.get(f"/chat/sessions/{session['id']}", headers=other).status_code == 404
    assert client.patch(f"/chat/sessions/{session['id']}", headers=headers, json={}).status_code == 400


def test_session_survives_restart(monkeypatch, tmp_path):
    module, client, headers, other = _setup(monkeypatch, tmp_path)
    session = client.post("/chat/sessions", headers=headers, json={"title": "persistent"}).json()
    client.post(f"/chat/sessions/{session['id']}/messages", headers=headers, json={"content": "still here"})
    # simulate application restart against the same file-backed database
    module.store.configure(str(tmp_path / "chat.db"))
    listing = client.get("/chat/sessions", headers=headers).json()
    assert listing[0]["title"] == "persistent" and listing[0]["message_count"] == 2
    assert len(client.get(f"/chat/sessions/{session['id']}/messages", headers=headers).json()) == 2
