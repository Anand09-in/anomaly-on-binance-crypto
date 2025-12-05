import asyncio
import logging
import signal
import sys
from datetime import datetime, timezone
from typing import List

from config import Settings
from binance_ws import binance_combined_stream
from kafka_producer import KafkaWriter
from aggregator import MultiWindowAggregator
from metrics import start_metrics_server, MSG_PRODUCED, MSG_RECEIVED, MSG_PRODUCER_ERRORS, CONNECTED_WS

settings = Settings()
log = logging.getLogger("producer")


async def _producer_loop(symbols: List[str], writer: KafkaWriter, agg: MultiWindowAggregator, stop_event: asyncio.Event):
    """
    Main loop: read from Binance combined stream and produce raw messages and add to aggregator.
    """
    # Use one combined stream for all symbols
    stream = binance_combined_stream(symbols)
    try:
        async for normalized in stream:
            if stop_event.is_set():
                break
            symbol = normalized["symbol"]
            price = normalized["price"]
            qty = normalized["qty"]
            ts_ms = normalized["ts_ms"]

            # metrics
            try:
                MSG_RECEIVED.labels(symbol=symbol).inc()
            except Exception:
                log.exception("metrics inc failed on receive")

            # produce raw
            raw_payload = {
                "symbol": symbol,
                "price": price,
                "qty": qty,
                "ts": ts_ms,
                "ingest_ts": int(datetime.now(timezone.utc).timestamp() * 1000),
                "raw": normalized.get("raw"),
            }
            try:
                await writer.send(settings.KAFKA_RAW_TOPIC, raw_payload, key=symbol.encode())
                MSG_PRODUCED.labels(topic=settings.KAFKA_RAW_TOPIC, symbol=symbol).inc()
            except Exception:
                log.exception("Failed to send raw payload to Kafka")
                MSG_PRODUCER_ERRORS.labels(stage="send_raw").inc()

            # add to aggregator
            await agg.add_trade(symbol, price, qty, ts_ms)

    except asyncio.CancelledError:
        log.info("producer loop cancelled")
    except Exception:
        log.exception("producer loop crashed")
    finally:
        log.info("producer loop exiting")


async def _flush_loop(writer: KafkaWriter, agg: MultiWindowAggregator, stop_event: asyncio.Event):
    """
    Periodically flush completed windows and produce kline messages. Also optionally push aggregated metrics to Kafka.
    """
    try:
        while not stop_event.is_set():
            ready = await agg.flush_ready()
            # ready: {window_seconds: {symbol: {start: Kline}}}
            for window_sec, sym_map in ready.items():
                topic = settings.KAFKA_KLINE_10S_TOPIC if window_sec == settings.AGG_WINDOW_SECONDS_10S else settings.KAFKA_KLINE_1M_TOPIC
                for symbol, buckets in sym_map.items():
                    for start, k in buckets.items():
                        payload = k.to_dict(symbol)
                        try:
                            await writer.send(topic, payload, key=symbol.encode())
                            MSG_PRODUCED.labels(topic=topic, symbol=symbol).inc()
                        except Exception:
                            log.exception("Failed to send kline payload to Kafka")
                            MSG_PRODUCER_ERRORS.labels(stage="send_kline").inc()
                        # optionally publish metrics to Kafka
                        if settings.METRICS_PUSH_TO_KAFKA and settings.KAFKA_METRICS_TOPIC:
                            try:
                                metric_payload = {
                                    "symbol": symbol,
                                    "window_sec": window_sec,
                                    "start_ts": k.start_ts,
                                    "count": k.count,
                                    "volume": k.volume,
                                    "open": k.open,
                                    "close": k.close,
                                    "high": k.high,
                                    "low": k.low,
                                }
                                await writer.send_metrics("kline", metric_payload)
                            except Exception:
                                log.exception("Failed to push kline metrics to kafka")
            await asyncio.sleep(1)
    except asyncio.CancelledError:
        log.info("flush loop cancelled")
    except Exception:
        log.exception("flush loop crashed")
    finally:
        log.info("flush loop exiting")


async def run():
    start_metrics_server()
    writer = KafkaWriter()
    await writer.start()

    symbols = settings.symbol_list
    log.info("Starting producer for symbols: %s", symbols)

    agg = MultiWindowAggregator(windows_seconds=(settings.AGG_WINDOW_SECONDS_10S, settings.AGG_WINDOW_SECONDS_1M))

    stop_event = asyncio.Event()

    producer_task = asyncio.create_task(_producer_loop(symbols, writer, agg, stop_event))
    flush_task = asyncio.create_task(_flush_loop(writer, agg, stop_event))

    # handle signals
    loop = asyncio.get_running_loop()

    def _on_sig(signame):
        log.info("Received signal %s, shutting down", signame)
        stop_event.set()
        for t in (producer_task, flush_task):
            t.cancel()

    for s in (signal.SIGINT, signal.SIGTERM):
        try:
            loop.add_signal_handler(s, lambda s=s: _on_sig(s.name))
        except NotImplementedError:
            # Windows event loop may not support add_signal_handler
            pass

    try:
        await asyncio.gather(producer_task, flush_task)
    finally:
        await writer.stop()


def _setup_logging():
    level = logging.DEBUG if settings.DEBUG else settings.LOG_LEVEL
    logging.basicConfig(level=level, format="%(asctime)s %(levelname)s %(name)s - %(message)s")


def main():
    _setup_logging()
    try:
        asyncio.run(run())
    except KeyboardInterrupt:
        log.info("KeyboardInterrupt received, exiting")
    except Exception:
        log.exception("Fatal error in main")
        sys.exit(1)


if __name__ == "__main__":
    main()
