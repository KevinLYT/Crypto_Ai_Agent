"""Request/response and domain models."""

from __future__ import annotations

from datetime import datetime
from typing import List, Literal, Optional

from pydantic import BaseModel, Field, field_validator, model_validator


class Transaction(BaseModel):
    """Single on-chain style transfer record (MVP: mock-friendly)."""

    timestamp: datetime
    from_address: str
    to_address: str
    amount: float = Field(ge=0)
    token: str
    tx_type: Literal["transfer", "swap", "contract_call", "other"] = "transfer"


class AnalyzeWalletRequest(BaseModel):
    """POST /analyze-wallet body."""

    wallet_address: Optional[str] = None
    mock_transactions: Optional[List[Transaction]] = None

    @field_validator("wallet_address")
    @classmethod
    def strip_wallet(cls, v: Optional[str]) -> Optional[str]:
        if v is None:
            return None
        s = v.strip()
        return s or None

    @model_validator(mode="after")
    def require_input(self) -> "AnalyzeWalletRequest":
        if not self.wallet_address and not self.mock_transactions:
            raise ValueError("必须提供 wallet_address 或 mock_transactions 之一")
        return self


class ExtractedFeatures(BaseModel):
    """Deterministic features passed to LLM / rules engine."""

    total_transactions: int
    total_amount_out: float
    total_amount_in: float
    net_flow: float
    average_transaction_amount: float
    large_transaction_count: int
    large_transaction_threshold: float
    unique_counterparty_count: int
    active_days: int
    transactions_per_active_day: float
    high_frequency_flag: bool
    high_frequency_notes: str


class AIAnalysis(BaseModel):
    """Structured output from LLM or local template."""

    wallet_summary: str
    risk_level: Literal["low", "medium", "high"]
    risk_reasons: List[str]
    unusual_patterns: List[str]
    suggested_followup: List[str]


class AnalyzeWalletResponse(BaseModel):
    """API envelope."""

    wallet_address: str
    extracted_features: ExtractedFeatures
    ai_analysis: AIAnalysis
