from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Dict, Optional, Tuple
import asyncio


@dataclass
class Kline:
    start_ts: int  # ms epoch for window start
    open: float
    high: float
    low: float
    close: float
    volume: float
    count: int

    def to_dict(self, symbol: str):
        return {
            "symbol": symbol,
            "start_ts": self.start_ts,
            "open": self.open,
            "high": self.high,
            "low": self.low,
            "close": self.close,
            "volume": self.volume,
            "count": self.count,
        }


class MultiWindowAggregator:
    """
    Maintains buckets per symbol for multiple window sizes.
    Example windows: 10s, 60s
    """
    def __init__(self, windows_seconds: Tuple[int, ...]):
        self.windows = windows_seconds
        # structure: { window_seconds: { symbol: { bucket_start_sec: Kline } } }
        self._store: Dict[int, Dict[str, Dict[int, Kline]]] = {w: {} for w in self.windows}
        self._lock = asyncio.Lock()

    def _bucket_start(self, ts_ms: int, window_seconds: int) -> int:
        ts = ts_ms // 1000
        return ts - (ts % window_seconds)

    async def add_trade(self, symbol: str, price: float, qty: float, ts_ms: int):
        async with self._lock:
            for w in self.windows:
                sym_store = self._store.setdefault(w, {})
                buckets = sym_store.setdefault(symbol, {})
                start = self._bucket_start(ts_ms, w)
                k = buckets.get(start)
                if k is None:
                    buckets[start] = Kline(
                        start_ts=start * 1000,
                        open=price, high=price, low=price, close=price, volume=qty, count=1
                    )
                else:
                    k.high = max(k.high, price)
                    k.low = min(k.low, price)
                    k.close = price
                    k.volume += qty
                    k.count += 1

    async def flush_ready(self) -> Dict[int, Dict[str, Dict[int, Kline]]]:
        """
        Return and remove buckets which window has ended (older than now).
        Return structure: {window_seconds: {symbol: {start: Kline}}}
        """
        now = int(datetime.now(timezone.utc).timestamp())
        out = {}
        async with self._lock:
            for w, sym_map in list(self._store.items()):
                ready_sym = {}
                for sym, buckets in list(sym_map.items()):
                    ready_buckets = {}
                    for start, k in list(buckets.items()):
                        if start + w <= now:
                            ready_buckets[start] = buckets.pop(start)
                    if ready_buckets:
                        ready_sym[sym] = ready_buckets
                    # cleanup empty symbol maps
                    if not buckets:
                        sym_map.pop(sym, None)
                if ready_sym:
                    out[w] = ready_sym
            # optional cleanup of empty windows
        return out
