"""API routes."""

from __future__ import annotations

import logging
from typing import Dict

from fastapi import APIRouter, HTTPException

from app.models.schemas import AnalyzeWalletRequest, AnalyzeWalletResponse
from app.services.ai_analysis import analyze_wallet_ai
from app.services.feature_extraction import extract_features
from app.services.mock_data import build_default_mock_transactions
from app.services.wallet_resolve import infer_wallet_from_transactions, resolve_wallet_address

logger = logging.getLogger(__name__)

router = APIRouter()


@router.get("/health")
async def health() -> Dict[str, str]:
    return {"status": "ok"}


@router.post("/analyze-wallet", response_model=AnalyzeWalletResponse)
async def analyze_wallet(body: AnalyzeWalletRequest) -> AnalyzeWalletResponse:
    """
    分析钱包：可传 wallet_address（自动 mock）、或传 mock_transactions。
    """
    try:
        if body.mock_transactions:
            txs = list(body.mock_transactions)
            wallet = (
                body.wallet_address.strip().lower()
                if body.wallet_address
                else infer_wallet_from_transactions(txs)
            )
        else:
            assert body.wallet_address is not None
            txs = build_default_mock_transactions(body.wallet_address)
            wallet = resolve_wallet_address(body.wallet_address, txs)
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
