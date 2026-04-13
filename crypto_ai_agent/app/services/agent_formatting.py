"""Post-processing and presentation helpers for the LangChain wallet agent."""

from __future__ import annotations

import json
import logging
from typing import Any, List, Optional

from app.models.agent_schemas import ToolTraceSummary
from app.models.schemas import AIAnalysis, ExtractedFeatures

logger = logging.getLogger(__name__)


def _safe_json_loads(text: str) -> Optional[Any]:
    s = text.strip()
    if not s:
        return None
    try:
        return json.loads(s)
    except json.JSONDecodeError:
        return None


def looks_like_json_object(text: str) -> bool:
    t = text.lstrip()
    return t.startswith("{") or t.startswith("[")


def parse_ai_analysis_from_text(text: str) -> Optional[AIAnalysis]:
    """
    Parse `AIAnalysis` from a tool observation or model output.

    Handles raw JSON objects and occasional double-encoded JSON strings.
    """
    if not text or not text.strip():
        return None

    data = _safe_json_loads(text)
    if data is None:
        return None

    if isinstance(data, str):
        inner = _safe_json_loads(data)
        if not isinstance(inner, dict):
            return None
        data = inner

    if not isinstance(data, dict):
        return None

    if "error" in data and len(data) <= 3:
        return None

    required = {"wallet_summary", "risk_level", "risk_reasons", "unusual_patterns", "suggested_followup"}
    if not required.issubset(data.keys()):
        return None

    try:
        return AIAnalysis.model_validate(data)
    except Exception as exc:  # noqa: BLE001
        logger.debug("AIAnalysis parse failed: %s", exc)
        return None


def extract_risk_from_intermediate_steps(steps: Any) -> Optional[AIAnalysis]:
    """Prefer the latest successful `assess_wallet_risk` tool observation."""
    if not steps:
        return None

    for action, observation in reversed(steps):
        tool = getattr(action, "tool", None) or ""
        if str(tool) != "assess_wallet_risk":
            continue
        obs = observation if isinstance(observation, str) else str(observation)
        parsed = parse_ai_analysis_from_text(obs)
        if parsed is not None:
            return parsed
    return None


def resolve_risk_assessment(
    run_state: dict[str, Any],
    intermediate_steps: Any,
    raw_agent_output: str,
) -> Optional[AIAnalysis]:
    """
    Resolve structured risk in priority order:
    1) captured in `run_state` during tool execution
    2) last `assess_wallet_risk` observation
    3) model final output if it is JSON shaped like `AIAnalysis`
    """
    rs = run_state.get("risk_assessment")
    if isinstance(rs, AIAnalysis):
        return rs

    from_steps = extract_risk_from_intermediate_steps(intermediate_steps)
    if from_steps is not None:
        return from_steps

    if raw_agent_output and looks_like_json_object(raw_agent_output):
        return parse_ai_analysis_from_text(raw_agent_output)

    return None


def summarize_get_wallet_transactions(observation: str) -> str:
    parsed = _safe_json_loads(observation)
    if isinstance(parsed, dict) and parsed.get("error"):
        return f"Could not load mock transactions: {parsed.get('error')}"
    if not isinstance(parsed, dict):
        return "Retrieved mock transaction history (details omitted)."

    txs = parsed.get("transactions")
    wallet = parsed.get("wallet_address", "")
    if isinstance(txs, list):
        n = len(txs)
        short = f"{wallet[:6]}…{wallet[-4:]}" if isinstance(wallet, str) and len(wallet) > 12 else wallet
        return f"Retrieved {n} mock transaction(s) for wallet {short or '(unknown)'}."
    return "Retrieved mock transaction payload (unusual shape)."


def summarize_extract_wallet_features(observation: str) -> str:
    parsed = _safe_json_loads(observation)
    if isinstance(parsed, dict) and parsed.get("error"):
        return f"Feature extraction failed: {parsed.get('error')}"
    if not isinstance(parsed, dict):
        return "Extracted behavioral features (details omitted)."

    n = parsed.get("total_transactions")
    net = parsed.get("net_flow")
    peers = parsed.get("unique_counterparty_count")
    parts: List[str] = ["Extracted wallet-level statistics"]
    if isinstance(n, int):
        parts.append(f"{n} transaction(s)")
    if net is not None:
        parts.append(f"net flow ≈ {net}")
    if isinstance(peers, int):
        parts.append(f"{peers} unique counterparties")
    return ", ".join(parts) + "."


def summarize_assess_wallet_risk(observation: str) -> str:
    parsed = parse_ai_analysis_from_text(observation)
    if parsed is not None:
        return (
            f"Generated a {parsed.risk_level} risk assessment "
            f"({len(parsed.risk_reasons)} reason(s), {len(parsed.suggested_followup)} follow-up suggestion(s))."
        )

    raw = _safe_json_loads(observation)
    if isinstance(raw, dict) and raw.get("error"):
        return f"Risk assessment failed: {raw.get('error')}"

    return "Completed risk assessment step (output not in expected structured form)."


def summarize_tool_observation(tool_name: str, observation: str) -> str:
    name = str(tool_name)
    obs = observation if isinstance(observation, str) else str(observation)
    if name == "get_wallet_transactions":
        return summarize_get_wallet_transactions(obs)
    if name == "extract_wallet_features":
        return summarize_extract_wallet_features(obs)
    if name == "assess_wallet_risk":
        return summarize_assess_wallet_risk(obs)
    if len(obs) > 240:
        return f"Ran {name}; output length {len(obs)} (omitted)."
    return f"Ran {name}."


def build_tool_trace_summaries(steps: Any) -> List[ToolTraceSummary]:
    out: List[ToolTraceSummary] = []
    if not steps:
        return out

    for action, observation in steps:
        tool_name = getattr(action, "tool", None) or "unknown_tool"
        obs = observation if isinstance(observation, str) else str(observation)
        out.append(
            ToolTraceSummary(
                tool=str(tool_name),
                summary=summarize_tool_observation(str(tool_name), obs),
            )
        )
    return out


def _join_bullets(items: List[str], limit: int = 4) -> str:
    xs = [x.strip() for x in items if x and x.strip()]
    if not xs:
        return ""
    head = xs[:limit]
    more = len(xs) - len(head)
    s = "; ".join(head)
    if more > 0:
        s += f" (+{more} more)"
    return s


def derive_agent_answer(
    *,
    question: str,
    wallet_address: str,
    raw_model_output: str,
    risk: Optional[AIAnalysis],
    extracted_features: Optional[ExtractedFeatures],
) -> str:
    """
    Choose a stable, UI-friendly final string.

    Prefer structured `risk_assessment` grounding; fall back to non-JSON model text.
    """
    if risk is not None:
        return build_natural_language_answer(
            question,
            risk,
            wallet_address=wallet_address,
            extracted_features=extracted_features,
            raw_model_answer=raw_model_output,
        )

    raw = (raw_model_output or "").strip()
    if raw and not looks_like_json_object(raw):
        return raw

    parsed = parse_ai_analysis_from_text(raw)
    if parsed is not None:
        return build_natural_language_answer(
            question,
            parsed,
            wallet_address=wallet_address,
            extracted_features=extracted_features,
            raw_model_answer="",
        )

    return raw or "（模型未返回可用的自然语言说明；可检查工具调用是否完整。）"


def build_natural_language_answer(
    question: str,
    risk: AIAnalysis,
    *,
    wallet_address: str,
    extracted_features: Optional[ExtractedFeatures] = None,
    raw_model_answer: str = "",
) -> str:
    """
    Produce a concise end-user answer grounded in `risk_assessment`.

    If the model already produced clean prose (not JSON), prefer it when risk is missing;
    when risk exists, we still synthesize a stable product-style paragraph.
    """
    _ = question  # reserved for future tone/locale routing
    short_wallet = wallet_address if len(wallet_address) <= 14 else f"{wallet_address[:6]}…{wallet_address[-4:]}"

    level = risk.risk_level
    level_phrase = {
        "low": "relatively low risk",
        "medium": "moderate risk",
        "high": "elevated risk",
    }.get(level, f"{level} risk")

    reasons = _join_bullets(risk.risk_reasons, limit=3)
    follow = _join_bullets(risk.suggested_followup, limit=2)

    parts: List[str] = [
        f"This wallet ({short_wallet}) appears to show {level_phrase} based on the analyzed sample.",
    ]

    summary = risk.wallet_summary.strip()
    if summary:
        parts.append(summary)

    if reasons:
        parts.append(f"Key drivers include: {reasons}.")

    if extracted_features and extracted_features.total_transactions:
        parts.append(
            f"The sample contains {extracted_features.total_transactions} transaction(s) "
            f"across {extracted_features.active_days} active day(s)."
        )

    if follow:
        parts.append(f"Suggested next checks: {follow}.")

    merged = " ".join(p for p in parts if p).strip()

    raw = (raw_model_answer or "").strip()
    if raw and not looks_like_json_object(raw) and len(raw) > 40:
        # Blend model tone with structured grounding (short add-on).
        if raw not in merged and raw[:120] not in merged:
            merged = f"{merged} {raw}".strip()

    return merged


__all__ = [
    "build_natural_language_answer",
    "build_tool_trace_summaries",
    "derive_agent_answer",
    "extract_risk_from_intermediate_steps",
    "looks_like_json_object",
    "parse_ai_analysis_from_text",
    "resolve_risk_assessment",
    "summarize_tool_observation",
]
