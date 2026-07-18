"""
Binance anomaly detection — PyFlink 1.18 streaming job.

Pipeline:
  Kafka kline-10s  →  feature computation  →  anomaly scoring  →  Postgres
                                                                 →  Kafka anomaly-alerts

Run (inside flink-jobmanager container):
    python /opt/anomaly/streaming/flink_job.py
"""
from __future__ import annotations

import json
import logging
import os
from collections import deque
from datetime import datetime, timezone
from typing import Iterator

import psycopg
from pyflink.common import SimpleStringSchema, WatermarkStrategy
from pyflink.datastream import StreamExecutionEnvironment
from pyflink.datastream.connectors.kafka import (
    KafkaOffsetsInitializer,
    KafkaSource,
)
from pyflink.datastream.functions import KeyedProcessFunction, RuntimeContext
from pyflink.datastream.state import ListStateDescriptor
from pyflink.common.typeinfo import Types

log = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s - %(message)s")

# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------
KAFKA_SERVERS  = os.getenv("KAFKA_BOOTSTRAP_SERVERS", "kafka:29092")
POSTGRES_DSN   = os.getenv("POSTGRES_DSN", "postgresql://anomaly:anomaly@postgres:5432/anomaly")
KLINE_TOPIC    = os.getenv("KAFKA_KLINE_TOPIC", "kline-10s")
ANOMALY_TOPIC  = os.getenv("KAFKA_ANOMALY_TOPIC", "anomaly-alerts")
MLFLOW_URI     = os.getenv("MLFLOW_TRACKING_URI", "http://mlflow:5000")

PRICE_SPIKE_PCT   = float(os.getenv("PRICE_SPIKE_PCT", "2.0"))
VOLUME_SPIKE_MULT = float(os.getenv("VOLUME_SPIKE_MULT", "5.0"))
ROLLING_WINDOW    = int(os.getenv("ROLLING_WINDOW", "30"))

WINDOW_SEC = 10  # each kline spans 10 s


# ---------------------------------------------------------------------------
# Parsing
# ---------------------------------------------------------------------------

def parse_kline(raw: str) -> dict | None:
    try:
        msg = json.loads(raw)
        symbol   = msg["symbol"]
        start_ts = int(msg["start_ts"])
        open_p   = float(msg["open"])
        high_p   = float(msg["high"])
        low_p    = float(msg["low"])
        close_p  = float(msg["close"])
        volume   = float(msg["volume"])
        count    = int(msg["count"])

        window_start = datetime.fromtimestamp(start_ts / 1000, tz=timezone.utc)
        window_end   = datetime.fromtimestamp((start_ts + WINDOW_SEC * 1000) / 1000, tz=timezone.utc)

        price_change_pct = ((close_p - open_p) / open_p * 100) if open_p else 0.0
        price_range_pct  = ((high_p - low_p) / low_p * 100) if low_p else 0.0
        buy_pressure     = close_p - open_p

        return {
            "symbol": symbol,
            "window_start": window_start.isoformat(),
            "window_end":   window_end.isoformat(),
            "open_price":   open_p,
            "high_price":   high_p,
            "low_price":    low_p,
            "close_price":  close_p,
            "volume":       volume,
            "trade_count":  count,
            "price_change_pct": price_change_pct,
            "price_range_pct":  price_range_pct,
            "buy_pressure":     buy_pressure,
        }
    except Exception:
        log.exception("Failed to parse kline: %.200s", raw)
        return None


# ---------------------------------------------------------------------------
# Anomaly detector (stateful, keyed by symbol)
# ---------------------------------------------------------------------------

class AnomalyDetector(KeyedProcessFunction):
    """
    Maintains a rolling window of recent price_change_pct and volume values
    per symbol.  Emits (feature_dict, alert_dict | None) tuples.
    """

    def open(self, ctx: RuntimeContext):
        self._price_state  = ctx.get_list_state(
            ListStateDescriptor("price_changes", Types.FLOAT()))
        self._volume_state = ctx.get_list_state(
            ListStateDescriptor("volumes", Types.FLOAT()))
        self._model = self._load_model()

    def _load_model(self):
        try:
            import mlflow
            mlflow.set_tracking_uri(MLFLOW_URI)
            client = mlflow.MlflowClient()
            mv = client.get_latest_versions("binance-isolation-forest", stages=["Production"])
            if mv:
                model = mlflow.sklearn.load_model(mv[0].source)
                log.info("Loaded Isolation Forest model from MLflow (version %s)", mv[0].version)
                return model
        except Exception:
            log.info("No MLflow model found; using rule-based detection only")
        return None

    def process_element(self, feature: dict, ctx: KeyedProcessFunction.Context) -> Iterator[tuple]:
        price_change = feature["price_change_pct"]
        volume       = feature["volume"]

        # Update rolling state
        prices  = list(self._price_state.get() or [])
        volumes = list(self._volume_state.get() or [])
        prices.append(price_change)
        volumes.append(volume)
        if len(prices)  > ROLLING_WINDOW: prices  = prices[-ROLLING_WINDOW:]
        if len(volumes) > ROLLING_WINDOW: volumes = volumes[-ROLLING_WINDOW:]
        self._price_state.update(prices)
        self._volume_state.update(volumes)

        alert = None

        # Rule-based detection
        if abs(price_change) > PRICE_SPIKE_PCT:
            avg_vol = sum(volumes[:-1]) / len(volumes[:-1]) if len(volumes) > 1 else volume
            alert = {
                "symbol":       feature["symbol"],
                "window_start": feature["window_start"],
                "alert_type":   "price_spike",
                "metric_value": price_change,
                "threshold":    PRICE_SPIKE_PCT,
                "anomaly_score": None,
            }

        elif len(volumes) >= 5:
            avg_vol = sum(volumes[:-1]) / len(volumes[:-1])
            if avg_vol > 0 and volume > avg_vol * VOLUME_SPIKE_MULT:
                alert = {
                    "symbol":       feature["symbol"],
                    "window_start": feature["window_start"],
                    "alert_type":   "volume_surge",
                    "metric_value": volume / avg_vol,
                    "threshold":    VOLUME_SPIKE_MULT,
                    "anomaly_score": None,
                }

        # ML scoring (if model loaded and enough history)
        if self._model is not None and len(prices) >= 10:
            import numpy as np
            avg_vol = sum(volumes) / len(volumes) if volumes else 1.0
            vol_ratio = volume / avg_vol if avg_vol else 1.0
            X = np.array([[price_change, feature["price_range_pct"], vol_ratio]])
            score = float(self._model.decision_function(X)[0])
            if score < -0.1:
                if alert is None:
                    alert = {
                        "symbol":       feature["symbol"],
                        "window_start": feature["window_start"],
                        "alert_type":   "pattern_anomaly",
                        "metric_value": score,
                        "threshold":    -0.1,
                        "anomaly_score": score,
                    }
                else:
                    alert["anomaly_score"] = score

        yield (feature, alert)


# ---------------------------------------------------------------------------
# Postgres sink
# ---------------------------------------------------------------------------

class PostgresSink:
    def __init__(self, dsn: str):
        self._dsn  = dsn
        self._conn = None

    def _ensure(self):
        if self._conn is None or self._conn.closed:
            self._conn = psycopg.connect(self._dsn, autocommit=True)

    def write_feature(self, f: dict):
        self._ensure()
        self._conn.execute(
            """
            INSERT INTO kline_features
                (symbol, window_start, window_end,
                 open_price, high_price, low_price, close_price,
                 volume, trade_count,
                 price_change_pct, price_range_pct, buy_pressure)
            VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
            ON CONFLICT (symbol, window_start) DO UPDATE SET
                close_price       = EXCLUDED.close_price,
                price_change_pct  = EXCLUDED.price_change_pct,
                updated_at        = NOW()
            """,
            (
                f["symbol"], f["window_start"], f["window_end"],
                f["open_price"], f["high_price"], f["low_price"], f["close_price"],
                f["volume"], f["trade_count"],
                f["price_change_pct"], f["price_range_pct"], f["buy_pressure"],
            ),
        )

    def write_alert(self, a: dict):
        self._ensure()
        self._conn.execute(
            """
            INSERT INTO anomaly_alerts
                (symbol, window_start, alert_type, metric_value, threshold, anomaly_score)
            VALUES (%s,%s,%s,%s,%s,%s)
            """,
            (
                a["symbol"], a["window_start"], a["alert_type"],
                a["metric_value"], a["threshold"], a["anomaly_score"],
            ),
        )


# ---------------------------------------------------------------------------
# Flink sink function wrapper
# ---------------------------------------------------------------------------

from pyflink.datastream.functions import SinkFunction

class PgSinkFunction(SinkFunction):
    def __init__(self, dsn: str):
        super().__init__()
        self._dsn  = dsn
        self._sink = None

    def open(self, ctx):
        self._sink = PostgresSink(self._dsn)

    def invoke(self, pair: tuple, ctx):
        feature, alert = pair
        try:
            self._sink.write_feature(feature)
            if alert:
                self._sink.write_alert(alert)
        except Exception:
            log.exception("Postgres write failed")


# ---------------------------------------------------------------------------
# Dead-letter sink
# ---------------------------------------------------------------------------

class DeadLetterSink(SinkFunction):
    def invoke(self, value, ctx):
        log.warning("Dead-letter: %.300s", value)


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    env = StreamExecutionEnvironment.get_execution_environment()
    env.set_parallelism(1)

    kafka_source = (
        KafkaSource.builder()
        .set_bootstrap_servers(KAFKA_SERVERS)
        .set_topics(KLINE_TOPIC)
        .set_group_id("flink-anomaly-detector")
        .set_starting_offsets(KafkaOffsetsInitializer.latest())
        .set_value_only_deserializer(SimpleStringSchema())
        .build()
    )

    raw_stream = env.from_source(
        kafka_source,
        WatermarkStrategy.no_watermarks(),
        "KlineKafkaSource",
    )

    # Parse
    parsed = raw_stream.map(parse_kline, output_type=Types.PICKLED_BYTE_ARRAY())
    good   = parsed.filter(lambda x: x is not None)
    bad    = parsed.filter(lambda x: x is None)

    bad.add_sink(DeadLetterSink())

    # Detect anomalies (stateful, keyed by symbol)
    results = (
        good
        .key_by(lambda f: f["symbol"], key_type=Types.STRING())
        .process(AnomalyDetector(), output_type=Types.PICKLED_BYTE_ARRAY())
    )

    # Write to Postgres
    results.add_sink(PgSinkFunction(POSTGRES_DSN))

    env.execute("binance-anomaly-detector")


if __name__ == "__main__":
    main()
