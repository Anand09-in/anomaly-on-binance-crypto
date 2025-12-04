# binance_ws.py
import asyncio
import json
import time
import websockets
from typing import List

BASE = "wss://stream.binance.com:9443/ws"   # raw socket for SUBSCRIBE/UNSUBSCRIBE
# Or to open a combined stream directly:
# BASE_COMBINED = "wss://stream.binance.com:9443/stream?streams=btcusdt@trade/ethusdt@trade"

async def subscribe(ws, streams: List[str], req_id: int = 1):
    payload = {
        "method": "SUBSCRIBE",
        "params": streams,
        "id": req_id
    }
    await ws.send(json.dumps(payload))

async def unsubscribe(ws, streams: List[str], req_id: int = 2):
    payload = {
        "method": "UNSUBSCRIBE",
        "params": streams,
        "id": req_id
    }
    await ws.send(json.dumps(payload))

async def handle_message(msg):
    # msg is a JSON string from Binance. You can parse and route by "e" (event).
    data = json.loads(msg)
    # Combined stream responses use {"stream": "...","data": {...}} format,
    # while raw streams push the raw payload directly.
    if isinstance(data, dict) and "stream" in data and "data" in data:
        payload = data["data"]
    else:
        payload = data

    # Basic routing example:
    ev = payload.get("e")  # event type, e.g. 'trade', 'aggTrade', 'kline'
    if ev == "trade":
        # example: print price + quantity
        print(f"TRADE {payload.get('s')} price={payload.get('p')} qty={payload.get('q')}")
    elif ev == "aggTrade":
        print(f"AGGTRADE {payload.get('s')} price={payload.get('p')} qty={payload.get('q')}")
    elif ev == "kline":
        k = payload.get("k", {})
        print(f"KLINE {payload.get('s')} interval={k.get('i')} close={k.get('c')} isClosed={k.get('x')}")
    else:
        # other events, including subscription confirmations: {"result":null,"id":1}
        print("MSG:", payload)

async def stream_loop():
    # reconnect loop
    while True:
        try:
            async with websockets.connect(BASE, ping_interval=None) as ws:
                print("Connected to Binance WS")

                # Example: dynamically subscribe to BTC and ETH trades and a kline
                await subscribe(ws, ["ethusdt@kline_10000ms"], req_id=1)

                # Track time to enforce a reconnect before 24h or handle server disconnects
                start = time.time()
                while True:
                    # set a short timeout on recv so we can check reconnect condition periodically
                    try:
                        msg = await asyncio.wait_for(ws.recv(), timeout=30)
                        # websockets library responds to pings automatically by default,
                        # but Binance sends ping frames — ensure the library/pings are handled.
                        await handle_message(msg)
                    except asyncio.TimeoutError:
                        # no message in 30s, send an unsolicited pong if desired (optional)
                        # The Binance docs allow unsolicited pongs but won't prevent disconnection.
                        # We'll send a lightweight ping to keep the connection healthy:
                        try:
                            await ws.ping()
                        except Exception:
                            break

                    # Reconnect proactively at ~23.5 hours (server may disconnect at 24h)
                    if time.time() - start > 23.5 * 3600:
                        print("Reconnecting proactively (24h limit)...")
                        break

        except Exception as e:
            print("WS error:", e)

        # backoff before reconnect
        await asyncio.sleep(5)

if __name__ == "__main__":
    asyncio.run(stream_loop())
