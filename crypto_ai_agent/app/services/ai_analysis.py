"""
LLM analysis layer.

切换方式（摘要）：
- 未设置环境变量 OPENAI_API_KEY（或为空）：自动走 `rule_based_analysis`。
- 已设置：走 `openai_analysis`（HTTP 调用 OpenAI Chat Completions）。
- 自定义兼容端点：设置 OPENAI_BASE_URL（例如部分代理或 Azure 需另行适配）。
"""

from __future__ import annotations

import json
import logging
from typing import Any, Dict, List, Literal, Optional

import httpx

from app.models.schemas import AIAnalysis, ExtractedFeatures
from utils.config import Settings, get_settings

logger = logging.getLogger(__name__)


def rule_based_analysis(wallet_address: str, features: ExtractedFeatures) -> AIAnalysis:
    """Deterministic template when no API key is configured."""

    reasons: List[str] = []
    unusual: List[str] = []
    followups: List[str] = []

    if features.total_transactions == 0:
        return AIAnalysis(
            wallet_summary="该地址在提供的样本中没有任何交易，无法评估行为模式。",
            risk_level="low",
            risk_reasons=["无交易数据"],
            unusual_patterns=["空地址或数据窗口内无活动"],
            suggested_followup=["接入真实链上索引后重新拉取全量历史"],
        )

    if features.large_transaction_count >= 2:
        reasons.append("出现多笔相对大额交易，需关注资金来源/去向是否集中")
        unusual.append("大额交易相对均值显著偏高")
        followups.append("对大额对手方地址做标签查询（交易所/混币器/合约）")

    if features.high_frequency_flag:
        reasons.append("触发高频或短时间密集成交启发式，可能与 bot、刷单或钓鱼有关")
        unusual.append(features.high_frequency_notes)
        followups.append("拉取更细粒度时间线并比对已知钓鱼模式")

    if features.net_flow < -features.total_amount_in * 0.5 and features.total_amount_in > 0:
        reasons.append("净流出显著，存在资金快速转出的形态")
        unusual.append("收入后短时间内大量转出")
        followups.append("检查是否存在分层转账（peeling chain）")

    if not reasons:
        reasons.append("未触发高风险启发式；样本量较小，结论仅供参考")
        unusual.append("交易模式较常规（基于当前 mock/样本）")
        followups.append("扩大时间窗口与代币维度后再评估")

    risk: Literal["low", "medium", "high"] = "low"
    if len(reasons) >= 3 or (features.large_transaction_count >= 2 and features.high_frequency_flag):
        risk = "high"
    elif len(reasons) >= 2 or features.high_frequency_flag or features.large_transaction_count >= 2:
        risk = "medium"

    short_addr = wallet_address if len(wallet_address) <= 12 else f"{wallet_address[:6]}...{wallet_address[-4:]}"
    summary = (
        f"地址 {short_addr} 在样本中共 {features.total_transactions} 笔交易，"
        f"净流入约 {features.net_flow:.2f}（按 token 混合加总，仅作演示），"
        f"与 {features.unique_counterparty_count} 个独立对手方发生过交互。"
    )

    return AIAnalysis(
        wallet_summary=summary,
        risk_level=risk,
        risk_reasons=reasons[:8],
        unusual_patterns=unusual[:8],
        suggested_followup=followups[:8],
    )


def _build_prompt(wallet_address: str, features: ExtractedFeatures) -> str:
    payload = features.model_dump()
    return (
        "你是区块链钱包安全分析助手。基于下列结构化特征，输出严格 JSON（不要 Markdown），"
        "字段：wallet_summary (string), risk_level ('low'|'medium'|'high'), "
        "risk_reasons (string array), unusual_patterns (string array), "
        "suggested_followup (string array)。\n"
        f"wallet_address: {wallet_address}\n"
        f"features: {json.dumps(payload, ensure_ascii=False)}"
    )


async def openai_analysis(
    wallet_address: str,
    features: ExtractedFeatures,
    settings: Settings,
) -> AIAnalysis:
    """
    调用 OpenAI Chat Completions（json_object）。

    生产环境可替换为：官方 SDK、Azure OpenAI、或其他兼容网关。
    """
    if not settings.openai_api_key:
        raise RuntimeError("OPENAI_API_KEY 未配置")

    url = settings.openai_base_url.rstrip("/") + "/chat/completions"
    headers = {
        "Authorization": f"Bearer {settings.openai_api_key}",
        "Content-Type": "application/json",
    }
    body: Dict[str, Any] = {
        "model": settings.openai_model,
        "temperature": 0.2,
        "response_format": {"type": "json_object"},
        "messages": [
            {
                "role": "system",
                "content": "你只输出合法 JSON，符合用户要求的字段。",
            },
            {"role": "user", "content": _build_prompt(wallet_address, features)},
        ],
    }

    async with httpx.AsyncClient(timeout=60.0) as client:
        resp = await client.post(url, headers=headers, json=body)
        resp.raise_for_status()
        data = resp.json()

    try:
        content = data["choices"][0]["message"]["content"]
        parsed = json.loads(content)
        return AIAnalysis.model_validate(parsed)
    except (KeyError, IndexError, json.JSONDecodeError, ValueError) as exc:
        logger.warning("OpenAI 返回解析失败，回退规则引擎: %s", exc)
        return rule_based_analysis(wallet_address, features)


async def analyze_wallet_ai(
    wallet_address: str,
    features: ExtractedFeatures,
    settings: Optional[Settings] = None,
) -> AIAnalysis:
    """
    统一入口：有 Key 走模型，否则模板。

    若 OpenAI 调用失败，同样回退到规则模板，保证接口可用。
    """
    cfg = settings or get_settings()
    if not cfg.openai_api_key:
        return rule_based_analysis(wallet_address, features)

    try:
        return await openai_analysis(wallet_address, features, cfg)
    except Exception as exc:  # noqa: BLE001 — MVP 宽泛兜底，记录后降级
        logger.exception("OpenAI 调用异常，回退规则引擎: %s", exc)
        return rule_based_analysis(wallet_address, features)
