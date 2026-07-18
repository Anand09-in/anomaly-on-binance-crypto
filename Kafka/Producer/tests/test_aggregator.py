import asyncio
import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from aggregator import MultiWindowAggregator


async def _test_basic():
    agg = MultiWindowAggregator(windows_seconds=(10, 60))
    ts_ms = 1_600_000_000_000  # fixed epoch ms

    await agg.add_trade("btcusdt", 100.0, 0.5, ts_ms)
    await agg.add_trade("btcusdt", 101.0, 0.2, ts_ms + 2_000)

    # Buckets for the 10s window
    store_10s = agg._store[10]
    assert "btcusdt" in store_10s

    bucket_start = ts_ms // 1000 - (ts_ms // 1000 % 10)
    k = store_10s["btcusdt"].get(bucket_start)
    assert k is not None, "Expected kline bucket to exist"
    assert k.open  == 100.0
    assert k.high  == 101.0
    assert k.low   == 100.0
    assert abs(k.volume - 0.7) < 1e-9
    assert k.count == 2


def test_multi_window_aggregator():
    asyncio.run(_test_basic())


async def _test_flush():
    agg = MultiWindowAggregator(windows_seconds=(10,))
    # Add a trade in a bucket that has already ended (epoch 0)
    await agg.add_trade("ethusdt", 3000.0, 1.0, 5_000)   # ts = 5s → bucket 0–10
    ready = await agg.flush_ready()
    # The bucket ends at ts=10 which is in the past → should be flushed
    assert 10 in ready
    assert "ethusdt" in ready[10]


def test_flush_ready():
    asyncio.run(_test_flush())
