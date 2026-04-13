"""Schemas for the LangChain agent API."""

from __future__ import annotations

from typing import List, Optional

from pydantic import BaseModel, Field, field_validator

from app.models.schemas import AIAnalysis, ExtractedFeatures


class AgentAnalyzeWalletRequest(BaseModel):
    """POST /agent/analyze-wallet body."""

    wallet_address: str = Field(..., min_length=1, description="Target wallet (hex-style string for MVP mocks).")
    question: str = Field(..., min_length=1, description="Natural-language question about the wallet.")

    @field_validator("wallet_address", "question")
    @classmethod
    def strip_non_empty(cls, v: str) -> str:
        s = v.strip()
        if not s:
            raise ValueError("must not be empty")
        return s


class ToolTraceSummary(BaseModel):
    """Human-readable summary of one tool invocation (product / debug friendly)."""

    tool: str
    summary: str


class AgentAnalyzeWalletResponse(BaseModel):
    """POST /agent/analyze-wallet response envelope."""

    wallet_address: str
    question: str
    agent_answer: str = Field(
        ...,
        description="Natural-language answer suitable for direct UI display.",
    )
    risk_assessment: Optional[AIAnalysis] = Field(
        default=None,
        description="Structured risk output (same shape as /analyze-wallet ai_analysis).",
    )
    extracted_features: Optional[ExtractedFeatures] = None
    tool_trace: List[ToolTraceSummary] = Field(default_factory=list)
    error: Optional[str] = None
