"""Compute wallet-level statistics from normalized transactions."""

from __future__ import annotations

from collections import defaultdict
from datetime import datetime
from typing import List, Optional

from app.models.schemas import ExtractedFeatures, Transaction
from utils.config import Settings, get_settings


def _mean(values: List[float]) -> float:
    if not values:
        return 0.0
    return sum(values) / len(values)


def _large_tx_threshold(amounts: List[float], settings: Settings) -> float:
    if not amounts:
        return 0.0
    avg = _mean(amounts)
    return max(avg * settings.large_tx_multiplier, 1e-9)


def _burst_high_frequency(
    timestamps: List[datetime],
    window_seconds: int,
    min_count: int,
) -> bool:
    if len(timestamps) < min_count:
        return False
    ts_sorted = sorted(timestamps)
    for i in range(len(ts_sorted)):
        start = ts_sorted[i]
        end_ts = start.timestamp() + window_seconds
        count = sum(1 for t in ts_sorted if start.timestamp() <= t.timestamp() <= end_ts)
        if count >= min_count:
            return True
    return False


def extract_features(
    wallet_address: str,
    transactions: List[Transaction],
    settings: Optional[Settings] = None,
) -> ExtractedFeatures:
    """
    Derive MVP features used by rules engine / LLM prompt.

    Extend with graph metrics, token breakdowns, contract labels, etc.
    """
    cfg = settings or get_settings()
    w = wallet_address.lower()

    if not transactions:
        return ExtractedFeatures(
            total_transactions=0,
            total_amount_out=0.0,
            total_amount_in=0.0,
            net_flow=0.0,
            average_transaction_amount=0.0,
            large_transaction_count=0,
            large_transaction_threshold=0.0,
            unique_counterparty_count=0,
            active_days=0,
            transactions_per_active_day=0.0,
            high_frequency_flag=False,
            high_frequency_notes="无交易记录",
        )

    amounts = [tx.amount for tx in transactions]
    threshold = _large_tx_threshold(amounts, cfg)
    large_count = sum(1 for a in amounts if a >= threshold)

    total_out = sum(tx.amount for tx in transactions if tx.from_address.lower() == w)
    total_in = sum(tx.amount for tx in transactions if tx.to_address.lower() == w)

    counterparties: set[str] = set()
    for tx in transactions:
        if tx.from_address.lower() == w:
            counterparties.add(tx.to_address.lower())
        if tx.to_address.lower() == w:
            counterparties.add(tx.from_address.lower())
    counterparties.discard(w)

    day_buckets: defaultdict[str, int] = defaultdict(int)
    for tx in transactions:
        day_key = tx.timestamp.date().isoformat()
        day_buckets[day_key] += 1
    active_days = len(day_buckets)
    txs_per_day = len(transactions) / active_days if active_days else 0.0

    burst = _burst_high_frequency(
        [tx.timestamp for tx in transactions],
        cfg.high_freq_burst_window_seconds,
        cfg.high_freq_burst_min_count,
    )
    high_rate = txs_per_day >= cfg.high_freq_tx_per_day
    high_frequency_flag = burst or high_rate

    notes_parts: list[str] = []
    if burst:
        notes_parts.append(
            f"在 {cfg.high_freq_burst_window_seconds}s 窗口内出现 >= {cfg.high_freq_burst_min_count} 笔交易"
        )
    if high_rate:
        notes_parts.append(
            f"活跃日平均交易数 {txs_per_day:.2f} >= {cfg.high_freq_tx_per_day}"
        )
    if not notes_parts:
        notes_parts.append("未触发高频启发式规则")

    return ExtractedFeatures(
        total_transactions=len(transactions),
        total_amount_out=round(total_out, 6),
        total_amount_in=round(total_in, 6),
        net_flow=round(total_in - total_out, 6),
        average_transaction_amount=round(_mean(amounts), 6),
        large_transaction_count=large_count,
        large_transaction_threshold=round(threshold, 6),
        unique_counterparty_count=len(counterparties),
        active_days=active_days,
        transactions_per_active_day=round(txs_per_day, 4),
        high_frequency_flag=high_frequency_flag,
        high_frequency_notes="; ".join(notes_parts),
    )
