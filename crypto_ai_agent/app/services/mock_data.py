"""Mock transaction generation when no real chain client is wired."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import List
import hashlib

from app.models.schemas import Transaction


def _stable_mock_address(seed: str) -> str:
    digest = hashlib.sha256(seed.encode("utf-8")).hexdigest()[:40]
    return f"0x{digest}"


def build_default_mock_transactions(wallet_address: str) -> List[Transaction]:
    """
    Produce a small, readable mock history for demos.
    Replace this module with a chain adapter later (Etherscan, Alchemy, etc.).
    """
    w = wallet_address.strip().lower()
    peer_a = _stable_mock_address(f"{w}-a")
    peer_b = _stable_mock_address(f"{w}-b")
    peer_c = _stable_mock_address(f"{w}-c")

    base = datetime(2024, 1, 1, 12, 0, tzinfo=timezone.utc)

    txs: List[Transaction] = [
        Transaction(
            timestamp=base,
            from_address=peer_a,
            to_address=w,
            amount=5000.0,
            token="USDT",
            tx_type="transfer",
        ),
        Transaction(
            timestamp=base + timedelta(hours=2),
            from_address=w,
            to_address=peer_b,
            amount=1200.0,
            token="USDT",
            tx_type="transfer",
        ),
        Transaction(
            timestamp=base + timedelta(hours=2, minutes=5),
            from_address=w,
            to_address=peer_b,
            amount=1180.0,
            token="USDT",
            tx_type="transfer",
        ),
        Transaction(
            timestamp=base + timedelta(days=1),
            from_address=w,
            to_address=peer_c,
            amount=9500.0,
            token="USDT",
            tx_type="transfer",
        ),
        Transaction(
            timestamp=base + timedelta(days=1, minutes=10),
            from_address=peer_c,
            to_address=w,
            amount=200.0,
            token="USDT",
            tx_type="transfer",
        ),
        Transaction(
            timestamp=base + timedelta(days=2),
            from_address=w,
            to_address=peer_a,
            amount=50.0,
            token="ETH",
            tx_type="swap",
        ),
    ]
    return txs
