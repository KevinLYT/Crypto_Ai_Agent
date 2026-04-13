from fastapi.testclient import TestClient

from app.main import app


def test_health() -> None:
    client = TestClient(app)
    r = client.get("/health")
    assert r.status_code == 200
    assert r.json()["status"] == "ok"


def test_analyze_wallet_mock_address() -> None:
    client = TestClient(app)
    r = client.post("/analyze-wallet", json={"wallet_address": "0xtestwallet0000000000000000000000000001"})
    assert r.status_code == 200
    body = r.json()
    assert "extracted_features" in body
    assert "ai_analysis" in body
    assert body["ai_analysis"]["risk_level"] in {"low", "medium", "high"}
