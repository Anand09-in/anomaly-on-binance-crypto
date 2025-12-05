import asyncio
import json
import logging
from typing import AsyncIterator
from websockets import connect
from config import Settings
from datetime import datetime, timezone

log = logging.getLogger(__name__)
settings = Settings()


def _stream_name(symbol: str, stream_type: str) -> str:
    s = symbol.lower()
    if stream_type == "trade":
        return f"{s}@trade"
    if stream_type == "aggTrade":
        return f"{s}@aggTrade"
    if stream_type == "miniTicker":
        return f"{s}@miniTicker"
    raise ValueError("unsupported stream type")


def build_combined_url(symbols: list, stream_type: str) -> str:
    streams = "/".join(_stream_name(s, stream_type) for s in symbols)
    return f"{settings.BINANCE_WS_BASE}?streams={streams}"


async def binance_combined_stream(symbols: list) -> AsyncIterator[dict]:
    """
    Connect to Binance combined websocket for multiple streams and yield normalized trade dicts:
    { "symbol": "btcusdt", "price": 123.4, "qty": 0.01, "ts_ms": 1234567890, "raw": {...} }
    Reconnects with exponential backoff on error.
    """
    url = build_combined_url(symbols, settings.WS_STREAM_TYPE)
    backoff = 1
    while True:
        try:
            log.info("Connecting to Binance combined WS: %s", url)
            async with connect(url, max_size=None) as ws:
                backoff = 1
                async for raw in ws:
                    try:
                        msg = json.loads(raw)
                        # combined stream wraps payload under 'data' and 'stream'
                        if "data" in msg and "stream" in msg:
                            data = msg["data"]
                        else:
                            data = msg
                        normalized = _normalize_message(data)
                        if normalized:
                            yield normalized
                    except Exception:
                        log.exception("Failed to decode/normalize message: %s", raw)
        except asyncio.CancelledError:
            raise
        except Exception:
            log.exception("Binance WS connection failed; reconnecting in %d seconds", backoff)
            await asyncio.sleep(backoff)
            backoff = min(backoff * 2, settings.MAX_WS_RECONNECT_BACKOFF)


def _normalize_message(msg: dict) -> dict:
    """
    Normalize incoming Binance message to common format.
    Handles 'trade' and 'aggTrade' types.
    """
    # Try to extract symbol from multiple possible keys
    symbol = (msg.get("s") or msg.get("S") or msg.get("symbol") or "").lower()
    try:
        if "p" in msg and "q" in msg and "T" in msg:
            price = float(msg.get("p"))
            qty = float(msg.get("q"))
            ts_ms = int(msg.get("T"))
        elif "price" in msg and "quantity" in msg and "timestamp" in msg:
            price = float(msg["price"])
            qty = float(msg["quantity"])
            ts_ms = int(msg["timestamp"])
        else:
            # best-effort fallback
            price = float(msg.get("p", msg.get("price", 0)))
            qty = float(msg.get("q", msg.get("quantity", 0)))
            ts_ms = int(msg.get("T", int(datetime.now(timezone.utc).timestamp() * 1000)))
    except Exception:
        log.exception("Error parsing message fields: %s", msg)
        return None

    return {"symbol": symbol, "price": price, "qty": qty, "ts_ms": ts_ms, "raw": msg}
