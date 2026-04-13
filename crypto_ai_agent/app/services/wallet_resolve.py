"""Resolve which address is the analysis subject."""

from __future__ import annotations

from collections import Counter
from typing import List, Optional

from app.models.schemas import Transaction


def infer_wallet_from_transactions(transactions: List[Transaction]) -> str:
    """
    MVP：从交易里推断“主钱包”（出现次数最多的地址）。
    生产环境应显式传入 wallet_address，避免误判多签/合约中转。
    """
    if not transactions:
        raise ValueError("mock_transactions 为空，无法推断钱包地址")

    counts: Counter[str] = Counter()
    for tx in transactions:
        counts[tx.from_address.lower()] += 1
        counts[tx.to_address.lower()] += 1
    wallet, _ = counts.most_common(1)[0]
    return wallet


def resolve_wallet_address(
    wallet_address: Optional[str],
    transactions: List[Transaction],
) -> str:
    if wallet_address:
        return wallet_address.strip().lower()
    return infer_wallet_from_transactions(transactions)
