"""Unit tests for agent response formatting (no OpenAI)."""

from __future__ import annotations

from app.models.schemas import AIAnalysis, ExtractedFeatures
from app.services.agent_formatting import (
    build_natural_language_answer,
    build_tool_trace_summaries,
    derive_agent_answer,
    looks_like_json_object,
    parse_ai_analysis_from_text,
    resolve_risk_assessment,
)


def test_parse_ai_analysis_from_text_roundtrip() -> None:
    analysis = AIAnalysis(
        wallet_summary="Demo summary",
        risk_level="medium",
        risk_reasons=["a", "b"],
        unusual_patterns=["u1"],
        suggested_followup=["f1"],
    )
    raw = analysis.model_dump_json()
    parsed = parse_ai_analysis_from_text(raw)
    assert parsed is not None
    assert parsed.risk_level == "medium"
    assert parsed.wallet_summary == "Demo summary"


def test_resolve_risk_prefers_run_state() -> None:
    analysis = AIAnalysis(
        wallet_summary="s",
        risk_level="low",
        risk_reasons=[],
        unusual_patterns=[],
        suggested_followup=[],
    )
    rs = {"risk_assessment": analysis}
    assert resolve_risk_assessment(rs, [], "{}") == analysis


def test_tool_trace_summaries_shape() -> None:
    txs_json = (
        '{"wallet_address":"0xabc","transactions":['
        '{"timestamp":"2024-01-01T12:00:00Z","from_address":"0xa","to_address":"0xabc",'
        '"amount":1,"token":"USDT","tx_type":"transfer"}]}'
    )
    feats = (
        '{"total_transactions":2,"total_amount_out":0,"total_amount_in":0,"net_flow":0,'
        '"average_transaction_amount":1,"large_transaction_count":0,"large_transaction_threshold":1,'
        '"unique_counterparty_count":1,"active_days":1,"transactions_per_active_day":2,'
        '"high_frequency_flag":false,"high_frequency_notes":"n"}'
    )
    risk = AIAnalysis(
        wallet_summary="x",
        risk_level="high",
        risk_reasons=["r1"],
        unusual_patterns=["u"],
        suggested_followup=["s1"],
    ).model_dump_json()

    class A:
        def __init__(self, tool: str):
            self.tool = tool

    steps = [
        (A("get_wallet_transactions"), txs_json),
        (A("extract_wallet_features"), feats),
        (A("assess_wallet_risk"), risk),
    ]
    trace = build_tool_trace_summaries(steps)
    assert len(trace) == 3
    assert all(hasattr(t, "tool") and hasattr(t, "summary") for t in trace)
    assert trace[0].tool == "get_wallet_transactions"
    assert "mock" in trace[0].summary.lower() or "Retrieved" in trace[0].summary
    assert trace[2].tool == "assess_wallet_risk"
    assert "high" in trace[2].summary.lower()


def test_derive_agent_answer_is_natural_language() -> None:
    risk = AIAnalysis(
        wallet_summary="Net flows look mixed.",
        risk_level="medium",
        risk_reasons=["Multiple large transfers"],
        unusual_patterns=["Burst activity"],
        suggested_followup=["Label counterparties"],
    )
    feats = ExtractedFeatures(
        total_transactions=6,
        total_amount_out=1.0,
        total_amount_in=1.0,
        net_flow=0.0,
        average_transaction_amount=1.0,
        large_transaction_count=0,
        large_transaction_threshold=1.0,
        unique_counterparty_count=2,
        active_days=2,
        transactions_per_active_day=3.0,
        high_frequency_flag=False,
        high_frequency_notes="n",
    )
    ans = derive_agent_answer(
        question="Is this wallet suspicious?",
        wallet_address="0xabcdefabcdefabcdefabcdefabcdefabcdefabcd",
        raw_model_output='{"wallet_summary":"ignored as json"}',
        risk=risk,
        extracted_features=feats,
    )
    assert isinstance(ans, str)
    assert looks_like_json_object(ans) is False
    assert "moderate risk" in ans.lower() or "medium" in ans.lower()


def test_risk_assessment_not_string_type() -> None:
    """`risk_assessment` should materialize as an object model, not a JSON string."""
    risk = AIAnalysis(
        wallet_summary="s",
        risk_level="low",
        risk_reasons=[],
        unusual_patterns=[],
        suggested_followup=[],
    )
    assert isinstance(risk.risk_level, str)
    dumped = risk.model_dump()
    assert isinstance(dumped["risk_reasons"], list)
