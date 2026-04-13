"""Minimal LangChain tool-calling agent for wallet Q&A (single turn)."""

from __future__ import annotations

import logging
from typing import Any, Optional, Sequence

from langchain.agents import AgentExecutor, create_tool_calling_agent
from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder
from langchain_openai import ChatOpenAI

from app.models.agent_schemas import AgentAnalyzeWalletResponse
from app.models.schemas import AIAnalysis, ExtractedFeatures
from app.services.agent_formatting import (
    build_tool_trace_summaries,
    derive_agent_answer,
    resolve_risk_assessment,
)
from app.services.agent_tools import build_wallet_tools
from utils.config import Settings, get_settings

logger = logging.getLogger(__name__)


class AgentConfigurationError(RuntimeError):
    """Raised when the LangChain agent cannot start (missing credentials, etc.)."""


def _require_openai_for_agent(settings: Settings) -> None:
    key = settings.openai_api_key
    if not key or not str(key).strip():
        raise AgentConfigurationError(
            "LangChain 智能体需要配置 OPENAI_API_KEY。"
            " 无 Key 时仍可使用 POST /analyze-wallet（规则或可选 OpenAI 分析）。"
        )


def _build_executor(
    settings: Settings,
    run_state: dict[str, Any],
    *,
    tools_override: Optional[Sequence[Any]] = None,
) -> AgentExecutor:
    tools = list(tools_override) if tools_override is not None else build_wallet_tools(run_state)

    llm = ChatOpenAI(
        model=settings.openai_model,
        api_key=settings.openai_api_key,
        base_url=settings.openai_base_url.rstrip("/"),
        temperature=0.2,
        timeout=90.0,
    )

    system = (
        "You are a blockchain wallet risk assistant. "
        "You have tools to load mock transactions, extract quantitative features, and assess risk. "
        "Use tools when they improve factual grounding. "
        "After tools, respond to the user in plain natural language (no JSON, no code fences) "
        "in the same language as the user's question. "
        "Do not paste raw tool JSON into the final answer; assume the API will attach structured fields. "
        "If tools return JSON with an 'error' field, explain the issue briefly and suggest fixes."
    )

    prompt = ChatPromptTemplate.from_messages(
        [
            ("system", system),
            (
                "human",
                "Target wallet (lowercased in tools if possible): {wallet_address}\n\n"
                "User question:\n{question}",
            ),
            MessagesPlaceholder("agent_scratchpad"),
        ]
    )

    agent = create_tool_calling_agent(llm, tools, prompt)
    return AgentExecutor(
        agent=agent,
        tools=tools,
        return_intermediate_steps=True,
        max_iterations=10,
        handle_parsing_errors=True,
        verbose=False,
    )


async def run_wallet_agent(
    wallet_address: str,
    question: str,
    *,
    settings: Optional[Settings] = None,
    tools_override: Optional[Sequence[Any]] = None,
) -> AgentAnalyzeWalletResponse:
    """
    Run a single-turn tool-calling agent.

    Unlike POST /analyze-wallet, the model decides tool usage based on the question.
    """
    cfg = settings or get_settings()
    _require_openai_for_agent(cfg)

    w = wallet_address.strip()
    q = question.strip()
    run_state: dict[str, Any] = {}
    executor = _build_executor(cfg, run_state, tools_override=tools_override)

    try:
        result = await executor.ainvoke({"wallet_address": w, "question": q})
    except Exception as exc:  # noqa: BLE001
        logger.exception("LangChain agent failed: %s", exc)
        raise

    raw_output = str(result.get("output") or "").strip()
    steps = result.get("intermediate_steps")

    risk: Optional[AIAnalysis] = resolve_risk_assessment(run_state, steps, raw_output)
    trace = build_tool_trace_summaries(steps)

    extracted: Optional[ExtractedFeatures] = None
    feat_any = run_state.get("extracted_features")
    if isinstance(feat_any, ExtractedFeatures):
        extracted = feat_any

    agent_answer = derive_agent_answer(
        question=q,
        wallet_address=w.lower(),
        raw_model_output=raw_output,
        risk=risk,
        extracted_features=extracted,
    )

    return AgentAnalyzeWalletResponse(
        wallet_address=w.lower(),
        question=q,
        agent_answer=agent_answer,
        risk_assessment=risk,
        extracted_features=extracted,
        tool_trace=trace,
    )


__all__ = [
    "AgentConfigurationError",
    "run_wallet_agent",
    "_build_executor",
]
