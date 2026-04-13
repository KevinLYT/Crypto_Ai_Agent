"""Tests for the LangChain agent endpoint."""

from __future__ import annotations

from typing import Any, Optional, Sequence

import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.models.agent_schemas import AgentAnalyzeWalletResponse, ToolTraceSummary
from app.models.schemas import AIAnalysis, ExtractedFeatures
from app.services.agent_formatting import looks_like_json_object
from utils.config import get_settings


@pytest.fixture()
def client() -> TestClient:
    return TestClient(app)


def test_agent_endpoint_validation(client: TestClient) -> None:
    r = client.post("/agent/analyze-wallet", json={"wallet_address": "0xabc", "question": ""})
    assert r.status_code == 422


def test_agent_missing_openai_key_returns_503(monkeypatch: pytest.MonkeyPatch, client: TestClient) -> None:
    monkeypatch.setenv("OPENAI_API_KEY", "")
    get_settings.cache_clear()

    r = client.post(
        "/agent/analyze-wallet",
        json={"wallet_address": "0x742d35Cc6634C0532925a3b844Bc9e7595f0bEb", "question": "Is this wallet suspicious?"},
    )
    assert r.status_code == 503
    detail = r.json().get("detail", "")
    assert "OPENAI_API_KEY" in detail
    assert "/analyze-wallet" in detail


def test_agent_success_schema_with_stub(monkeypatch: pytest.MonkeyPatch, client: TestClient) -> None:
    monkeypatch.setenv("OPENAI_API_KEY", "sk-test-not-real")
    get_settings.cache_clear()

    features = ExtractedFeatures(
        total_transactions=1,
        total_amount_out=1.0,
        total_amount_in=1.0,
        net_flow=0.0,
        average_transaction_amount=1.0,
        large_transaction_count=0,
        large_transaction_threshold=1.0,
        unique_counterparty_count=1,
        active_days=1,
        transactions_per_active_day=1.0,
        high_frequency_flag=False,
        high_frequency_notes="unit-test",
    )

    risk = AIAnalysis(
        wallet_summary="Stub summary for tests.",
        risk_level="low",
        risk_reasons=["stub reason"],
        unusual_patterns=["stub pattern"],
        suggested_followup=["stub follow-up"],
    )

    async def fake_run(
        wallet_address: str,
        question: str,
        *,
        settings: Optional[Any] = None,
        tools_override: Optional[Sequence[Any]] = None,
    ) -> AgentAnalyzeWalletResponse:
        return AgentAnalyzeWalletResponse(
            wallet_address=wallet_address.strip().lower(),
            question=question.strip(),
            agent_answer=(
                "This wallet (0xabc) appears to show relatively low risk based on the analyzed sample. "
                "Stub summary for tests."
            ),
            risk_assessment=risk,
            extracted_features=features,
            tool_trace=[
                ToolTraceSummary(tool="get_wallet_transactions", summary="Retrieved 1 mock transaction(s) for tests."),
                ToolTraceSummary(tool="extract_wallet_features", summary="Extracted wallet-level statistics."),
            ],
        )

    monkeypatch.setattr("app.api.routes.run_wallet_agent", fake_run)

    r = client.post(
        "/agent/analyze-wallet",
        json={
            "wallet_address": "0xAbC",
            "question": "Summarize this wallet’s behavior.",
        },
    )
    assert r.status_code == 200
    body = r.json()
    assert body["wallet_address"] == "0xabc"
    assert body["question"] == "Summarize this wallet’s behavior."
    assert isinstance(body["agent_answer"], str)
    assert looks_like_json_object(body["agent_answer"]) is False
    assert "low risk" in body["agent_answer"].lower() or "relatively low" in body["agent_answer"].lower()

    assert body["risk_assessment"] is not None
    assert isinstance(body["risk_assessment"], dict)
    assert body["risk_assessment"]["risk_level"] == "low"
    assert isinstance(body["risk_assessment"]["risk_reasons"], list)

    assert isinstance(body["tool_trace"], list)
    assert body["tool_trace"][0]["tool"] == "get_wallet_transactions"
    assert "summary" in body["tool_trace"][0]
    assert "mock" in body["tool_trace"][0]["summary"].lower() or "transaction" in body["tool_trace"][0]["summary"].lower()

    assert body["extracted_features"]["total_transactions"] == 1
