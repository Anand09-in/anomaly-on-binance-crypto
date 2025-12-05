import asyncio
from src.aggregator import WindowAggregator

async def test_aggregator_basic():
    agg = WindowAggregator(10)
    ts_ms = 1600000000000  # fixed timestamp in ms
    await agg.add_trade(100.0, 0.5, ts_ms)
    await agg.add_trade(101.0, 0.2, ts_ms + 2000)
    ready = await agg.flush_ready()
    # should not be ready yet because now() likely greater; but we can inspect bucket
    start = agg._bucket_start(ts_ms)
    k = agg._buckets.get(start)
    assert k is not None
    assert k.open == 100.0
    assert k.high == 101.0
    assert k.low == 100.0
    assert k.volume == 0.7

def test_sync():
    asyncio.run(test_aggregator_basic())
