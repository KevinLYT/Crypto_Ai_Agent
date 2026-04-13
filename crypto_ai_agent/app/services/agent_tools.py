"""LangChain tools wrapping existing wallet analysis primitives."""

from __future__ import annotations

import json
import logging
from typing import Any, Callable, List, MutableMapping, Optional, Tuple

from langchain_core.tools import StructuredTool
from pydantic import BaseModel, Field

from app.models.schemas import ExtractedFeatures, Transaction
from app.services.agent_formatting import parse_ai_analysis_from_text
from app.services.ai_analysis import analyze_wallet_ai
from app.services.feature_extraction import extract_features
from app.services.mock_data import build_default_mock_transactions
from app.services.wallet_resolve import resolve_wallet_address

logger = logging.getLogger(__name__)

_TOOL_OUTPUT_PREVIEW_LIMIT = 8000


def _truncate_for_trace(text: str, limit: int = _TOOL_OUTPUT_PREVIEW_LIMIT) -> str:
    if len(text) <= limit:
        return text
    return text[:limit] + f"\n... [truncated, total length {len(text)}]"


class GetWalletTransactionsInput(BaseModel):
    wallet_address: str = Field(..., description="Wallet address to load mock transactions for.")


class ExtractWalletFeaturesInput(BaseModel):
    wallet_address: str = Field(..., description="Subject wallet address used for in/out flow stats.")
    transactions_json: str = Field(
        ...,
        description=(
            "JSON string: either a list of transaction objects, or an object "
            '{"wallet_address": "...", "transactions": [...]} from get_wallet_transactions.'
        ),
    )


class AssessWalletRiskInput(BaseModel):
    wallet_address: str = Field(..., description="Subject wallet address for narrative context.")
    features_json: str = Field(..., description="JSON string of ExtractedFeatures from extract_wallet_features.")


def _parse_transactions_payload(transactions_json: str) -> Tuple[str, List[Transaction]]:
    raw = json.loads(transactions_json)
    if isinstance(raw, dict) and "transactions" in raw:
        wallet = str(raw.get("wallet_address", "")).strip().lower()
        txs_raw = raw["transactions"]
    elif isinstance(raw, list):
        wallet = ""
        txs_raw = raw
    else:
        raise ValueError("transactions_json must be a list or an object with key 'transactions'")

    if not isinstance(txs_raw, list):
        raise ValueError("'transactions' must be a JSON array")

    txs = [Transaction.model_validate(item) for item in txs_raw]
    return wallet, txs


async def _assess_wallet_risk_async(wallet_address: str, features_json: str) -> str:
    features = ExtractedFeatures.model_validate_json(features_json)
    w = wallet_address.strip().lower()
    analysis = await analyze_wallet_ai(w, features)
    return analysis.model_dump_json()


def build_wallet_tools(
    run_state: MutableMapping[str, Any],
    *,
    assess_fn: Optional[Callable[[str, str], Any]] = None,
) -> List[StructuredTool]:
    """
    Build tools for a single agent run.

    `run_state` is mutated to capture `extracted_features` when the extraction tool succeeds.
    `assess_fn` is injectable for tests (defaults to async OpenAI/rules analysis).
    """

    async def default_assess(wallet_address: str, features_json: str) -> str:
        return await _assess_wallet_risk_async(wallet_address, features_json)

    assess = assess_fn or default_assess

    def get_wallet_transactions(wallet_address: str) -> str:
        try:
            txs = build_default_mock_transactions(wallet_address)
            wallet = resolve_wallet_address(wallet_address.strip(), txs)
            payload = {
                "wallet_address": wallet,
                "transactions": [tx.model_dump(mode="json") for tx in txs],
            }
            return json.dumps(payload, ensure_ascii=False)
        except Exception as exc:  # noqa: BLE001
            logger.exception("get_wallet_transactions failed: %s", exc)
            return json.dumps({"error": str(exc)}, ensure_ascii=False)

    def extract_wallet_features(wallet_address: str, transactions_json: str) -> str:
        try:
            inferred_wallet, txs = _parse_transactions_payload(transactions_json)
            subject = wallet_address.strip().lower() or inferred_wallet
            if not subject:
                raise ValueError("wallet_address is required when transactions payload omits it")
            features = extract_features(subject, txs)
            run_state["extracted_features"] = features
            return features.model_dump_json()
        except Exception as exc:  # noqa: BLE001
            logger.exception("extract_wallet_features failed: %s", exc)
            return json.dumps({"error": str(exc)}, ensure_ascii=False)

    async def assess_wallet_risk(wallet_address: str, features_json: str) -> str:
        try:
            out = await assess(wallet_address, features_json)
            parsed = parse_ai_analysis_from_text(out)
            if parsed is not None:
                run_state["risk_assessment"] = parsed
            return out
        except Exception as exc:  # noqa: BLE001
            logger.exception("assess_wallet_risk failed: %s", exc)
            return json.dumps({"error": str(exc)}, ensure_ascii=False)

    tools = [
        StructuredTool.from_function(
            name="get_wallet_transactions",
            description=(
                "Load deterministic mock transactions for a wallet address. "
                "Returns JSON with keys wallet_address and transactions (array)."
            ),
            args_schema=GetWalletTransactionsInput,
            func=get_wallet_transactions,
        ),
        StructuredTool.from_function(
            name="extract_wallet_features",
            description=(
                "Compute structured behavioral features from transactions JSON. "
                "Pass the full JSON output from get_wallet_transactions, or a raw transaction array."
            ),
            args_schema=ExtractWalletFeaturesInput,
            func=extract_wallet_features,
        ),
        StructuredTool.from_function(
            name="assess_wallet_risk",
            description=(
                "Produce structured risk analysis (rules or OpenAI, depending on server configuration) "
                "from ExtractedFeatures JSON and the subject wallet address."
            ),
            args_schema=AssessWalletRiskInput,
            coroutine=assess_wallet_risk,
        ),
    ]
    return tools


def format_tool_input_preview(tool_input: Any) -> Any:
    """Normalize tool inputs for JSON responses."""
    if isinstance(tool_input, dict):
        return tool_input
    try:
        return json.loads(json.dumps(tool_input, default=str))
    except (TypeError, ValueError):
        return str(tool_input)


__all__ = ["build_wallet_tools", "format_tool_input_preview", "_truncate_for_trace"]
