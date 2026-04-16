"""API routes."""

from __future__ import annotations

import logging
from typing import Dict, List, Tuple

from fastapi import APIRouter, HTTPException

from app.models.agent_schemas import AgentAnalyzeWalletRequest, AgentAnalyzeWalletResponse
from app.models.schemas import AnalyzeWalletRequest, AnalyzeWalletResponse, Transaction
from app.services.agent_runner import AgentConfigurationError, run_wallet_agent
from app.services.ai_analysis import analyze_wallet_ai
from app.services.feature_extraction import extract_features
from app.services.mock_data import build_default_mock_transactions
from app.services.wallet_resolve import infer_wallet_from_transactions, resolve_wallet_address
from utils.config import get_settings

logger = logging.getLogger(__name__)

router = APIRouter()


def _resolve_analysis_input(body: AnalyzeWalletRequest) -> Tuple[str, List[Transaction]]:
    """
    Normalize request input into `(wallet_address, transactions)`.

    The runtime behavior is unchanged; this helper exists to keep the route thin
    and make the fixed pipeline steps easier to follow.
    """
    if body.mock_transactions:
        txs = list(body.mock_transactions)
        wallet = (
            body.wallet_address.strip().lower()
            if body.wallet_address
            else infer_wallet_from_transactions(txs)
        )
        return wallet, txs

    assert body.wallet_address is not None
    txs = build_default_mock_transactions(body.wallet_address)
    wallet = resolve_wallet_address(body.wallet_address, txs)
    return wallet, txs


@router.get("/health")
async def health() -> Dict[str, str]:
    return {"status": "ok"}


@router.post("/agent/analyze-wallet", response_model=AgentAnalyzeWalletResponse)
async def agent_analyze_wallet(body: AgentAnalyzeWalletRequest) -> AgentAnalyzeWalletResponse:
    """
    LangChain tool-calling agent: model chooses tools based on the question.

    Requires OPENAI_API_KEY (tool-calling + final answer). POST /analyze-wallet remains available without it.
    """
    try:
        settings = get_settings()
        logger.info("agent wallet analysis requested for wallet=%s", body.wallet_address.strip().lower())
        return await run_wallet_agent(body.wallet_address, body.question, settings=settings)
    except AgentConfigurationError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    except Exception as exc:  # noqa: BLE001
        logger.exception("agent analyze-wallet failed: %s", exc)
        raise HTTPException(status_code=502, detail="智能体执行失败，请稍后重试或查看日志。") from exc


@router.post("/analyze-wallet", response_model=AnalyzeWalletResponse)
async def analyze_wallet(body: AnalyzeWalletRequest) -> AnalyzeWalletResponse:
    """
    分析钱包：可传 wallet_address（自动 mock）、或传 mock_transactions。
    """
    try:
        wallet, txs = _resolve_analysis_input(body)
        logger.info("fixed wallet analysis requested for wallet=%s tx_count=%s", wallet, len(txs))
        features = extract_features(wallet, txs)
        analysis = await analyze_wallet_ai(wallet, features)

        return AnalyzeWalletResponse(
            wallet_address=wallet,
            extracted_features=features,
            ai_analysis=analysis,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception as exc:  # noqa: BLE001
        logger.exception("analyze-wallet failed: %s", exc)
        raise HTTPException(status_code=500, detail="内部错误，请稍后重试") from exc
