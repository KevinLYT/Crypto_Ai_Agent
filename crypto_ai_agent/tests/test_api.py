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


def test_analyze_wallet_infers_wallet_from_transactions() -> None:
    client = TestClient(app)
    r = client.post(
        "/analyze-wallet",
        json={
            "mock_transactions": [
                {
                    "timestamp": "2024-06-01T10:00:00Z",
                    "from_address": "0xaaa",
                    "to_address": "0xbbb",
                    "amount": 100.0,
                    "token": "USDT",
                    "tx_type": "transfer",
                },
                {
                    "timestamp": "2024-06-01T11:00:00Z",
                    "from_address": "0xbbb",
                    "to_address": "0xccc",
                    "amount": 60.0,
                    "token": "USDT",
                    "tx_type": "transfer",
                },
                {
                    "timestamp": "2024-06-01T12:00:00Z",
                    "from_address": "0xddd",
                    "to_address": "0xbbb",
                    "amount": 20.0,
                    "token": "USDT",
                    "tx_type": "transfer",
                },
            ]
        },
    )
    assert r.status_code == 200
    assert r.json()["wallet_address"] == "0xbbb"
