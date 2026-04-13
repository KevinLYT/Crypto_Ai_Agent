from datetime import datetime, timezone

from app.models.schemas import Transaction
from app.services.feature_extraction import extract_features
from app.services.wallet_resolve import infer_wallet_from_transactions
from utils.config import Settings


def test_extract_features_basic() -> None:
    w = "0xabc"
    txs = [
        Transaction(
            timestamp=datetime(2024, 1, 1, tzinfo=timezone.utc),
            from_address="0xpeer",
            to_address=w,
            amount=100.0,
            token="USDT",
            tx_type="transfer",
        ),
        Transaction(
            timestamp=datetime(2024, 1, 2, tzinfo=timezone.utc),
            from_address=w,
            to_address="0xpeer",
            amount=40.0,
            token="USDT",
            tx_type="transfer",
        ),
    ]
    settings = Settings(
        large_tx_multiplier=2.0,
        high_freq_tx_per_day=100.0,
        high_freq_burst_window_seconds=3600,
        high_freq_burst_min_count=10,
    )
    f = extract_features(w, txs, settings=settings)
    assert f.total_transactions == 2
    assert f.total_amount_in == 100.0
    assert f.total_amount_out == 40.0
    assert f.net_flow == 60.0


def test_infer_wallet() -> None:
    txs = [
        Transaction(
            timestamp=datetime(2024, 1, 1, tzinfo=timezone.utc),
            from_address="0xaaa",
            to_address="0xbbb",
            amount=1.0,
            token="ETH",
            tx_type="transfer",
        ),
        Transaction(
            timestamp=datetime(2024, 1, 2, tzinfo=timezone.utc),
            from_address="0xbbb",
            to_address="0xccc",
            amount=2.0,
            token="ETH",
            tx_type="transfer",
        ),
        Transaction(
            timestamp=datetime(2024, 1, 3, tzinfo=timezone.utc),
            from_address="0xddd",
            to_address="0xbbb",
            amount=3.0,
            token="ETH",
            tx_type="transfer",
        ),
    ]
    assert infer_wallet_from_transactions(txs) == "0xbbb"
