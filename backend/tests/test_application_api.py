from fastapi.testclient import TestClient


def test_health_and_auth_are_operational(monkeypatch, tmp_path):
    monkeypatch.setenv("TRUSTLINE_DB_PATH", str(tmp_path / "app.db"))
    from backend.api import app as module
    module.store.configure(str(tmp_path / "app.db"))
    client = TestClient(module.app)
    response = client.post("/auth/register", json={"username":"astro","password":"a-very-strong-password","role":"ASTRONAUT","astronaut_id":"AST-001"})
    assert response.status_code == 201
    login = client.post("/auth/login", json={"username":"astro","password":"a-very-strong-password"})
    assert login.status_code == 200
    token = login.json()["access_token"]
    assert client.get("/health").json()["status"] == "ok"
    assert client.get("/auth/me", headers={"Authorization": f"Bearer {token}"}).json()["astronaut_id"] == "AST-001"


def test_chat_persists_and_is_identity_isolated(monkeypatch, tmp_path):
    monkeypatch.setenv("TRUSTLINE_DB_PATH", str(tmp_path / "chat.db"))
    from backend.api import app as module
    module.store.configure(str(tmp_path / "chat.db"))
    client = TestClient(module.app)
    for username in ("astro1", "astro2"):
        assert client.post("/auth/register", json={"username":username,"password":"a-very-strong-password","role":"ASTRONAUT","astronaut_id":username.upper()}).status_code == 201
    token = client.post("/auth/login", json={"username":"astro1","password":"a-very-strong-password"}).json()["access_token"]
    headers = {"Authorization": f"Bearer {token}"}
    session = client.post("/chat/sessions", headers=headers, json={"title":"Mission check-in"}).json()
    assert client.post(f"/chat/sessions/{session['id']}/messages", headers=headers, json={"content":"hello"}).status_code == 201
    assert len(client.get(f"/chat/sessions/{session['id']}/messages", headers=headers).json()) == 2
    other_token = client.post("/auth/login", json={"username":"astro2","password":"a-very-strong-password"}).json()["access_token"]
    assert client.get(f"/chat/sessions/{session['id']}/messages", headers={"Authorization": f"Bearer {other_token}"}).status_code == 404


def test_demo_mode_is_separate(monkeypatch, tmp_path):
    monkeypatch.setenv("TRUSTLINE_DB_PATH", str(tmp_path / "demo.db"))
    from backend.api import app as module
    module.store.configure(str(tmp_path / "demo.db"))
    client = TestClient(module.app)
    headers = {"X-Trustline-Mode": "demo"}
    assert client.post("/auth/register", headers=headers, json={"username":"demo","password":"a-very-strong-password","role":"ASTRONAUT","astronaut_id":"DEMO-001"}).status_code == 201
    demo_token = client.post("/auth/login", headers=headers, json={"username":"demo","password":"a-very-strong-password"}).json()["access_token"]
    demo_headers = {**headers, "Authorization": f"Bearer {demo_token}"}
    assert client.post("/chat/sessions", headers=demo_headers, json={"title":"Synthetic"}).status_code == 201
    assert client.get("/chat/sessions", headers=demo_headers).json()[0]["is_demo"] is True
    assert client.post("/auth/login", json={"username":"demo","password":"a-very-strong-password"}).status_code == 401
