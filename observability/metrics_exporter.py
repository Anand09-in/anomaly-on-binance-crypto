"""
Prometheus metrics exporter for the Binance anomaly pipeline.
Scrapes Postgres every 15 s and exposes gauges on METRICS_PORT.

Run:
    python -m observability.metrics_exporter
"""
from __future__ import annotations

import logging
import os
import time

import psycopg
from prometheus_client import Gauge, Counter, start_http_server

log = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s - %(message)s")

POSTGRES_DSN  = os.getenv("POSTGRES_DSN", "postgresql://anomaly:anomaly@postgres:5432/anomaly")
MLFLOW_URI    = os.getenv("MLFLOW_TRACKING_URI", "http://mlflow:5000")
METRICS_PORT  = int(os.getenv("METRICS_PORT", "8000"))
SCRAPE_INTERVAL = int(os.getenv("SCRAPE_INTERVAL_S", "15"))

# ── Gauges ────────────────────────────────────────────────────────────────────
ACTIVE_ANOMALIES = Gauge(
    "anomaly_active_total",
    "Number of unresolved anomaly alerts",
    ["symbol"],
)
KLINES_TOTAL = Gauge(
    "kline_features_total",
    "Total kline_features rows in Postgres",
    ["symbol"],
)
ANOMALY_RATE_1H = Gauge(
    "anomaly_rate_1h",
    "Anomaly alerts in the last 1 hour",
    ["symbol", "alert_type"],
)
PIPELINE_LAG_S = Gauge(
    "pipeline_lag_seconds",
    "Seconds since the most recent kline_features window_end",
    ["symbol"],
)
MODEL_LAST_TRAINED = Gauge(
    "model_last_trained_timestamp",
    "Unix timestamp of the latest MLflow model registration",
)
DRIFT_PSI = Gauge(
    "drift_psi_score",
    "Latest Evidently PSI score per feature",
    ["feature"],
)


def _fetch(conn: psycopg.Connection, sql: str, params=()) -> list[tuple]:
    with conn.cursor() as cur:
        cur.execute(sql, params)
        return cur.fetchall()


def scrape_postgres(conn: psycopg.Connection) -> None:
    # Active anomalies per symbol
    rows = _fetch(conn, """
        SELECT symbol, COUNT(*) FROM anomaly_alerts
        WHERE resolved = FALSE
        GROUP BY symbol
    """)
    seen_symbols = set()
    for symbol, cnt in rows:
        ACTIVE_ANOMALIES.labels(symbol=symbol).set(cnt)
        seen_symbols.add(symbol)

    # Kline row counts per symbol
    rows = _fetch(conn, "SELECT symbol, COUNT(*) FROM kline_features GROUP BY symbol")
    for symbol, cnt in rows:
        KLINES_TOTAL.labels(symbol=symbol).set(cnt)
        if symbol not in seen_symbols:
            ACTIVE_ANOMALIES.labels(symbol=symbol).set(0)

    # Anomaly rate last 1 h
    rows = _fetch(conn, """
        SELECT symbol, alert_type, COUNT(*)
        FROM anomaly_alerts
        WHERE triggered_at > NOW() - INTERVAL '1 hour'
        GROUP BY symbol, alert_type
    """)
    for symbol, alert_type, cnt in rows:
        ANOMALY_RATE_1H.labels(symbol=symbol, alert_type=alert_type).set(cnt)

    # Pipeline lag per symbol
    rows = _fetch(conn, """
        SELECT symbol, EXTRACT(EPOCH FROM (NOW() - MAX(window_end)))
        FROM kline_features GROUP BY symbol
    """)
    for symbol, lag in rows:
        PIPELINE_LAG_S.labels(symbol=symbol).set(float(lag or 0))


def scrape_mlflow() -> None:
    try:
        import mlflow
        mlflow.set_tracking_uri(MLFLOW_URI)
        client = mlflow.MlflowClient()
        versions = client.get_latest_versions("binance-isolation-forest", stages=["Production"])
        if versions:
            # Use run end_time as proxy for training timestamp
            run = client.get_run(versions[0].run_id)
            ts = (run.info.end_time or 0) / 1000
            MODEL_LAST_TRAINED.set(ts)
    except Exception:
        log.debug("MLflow scrape failed (model may not exist yet)")


def scrape_drift() -> None:
    """Read latest drift JSON summary if available."""
    import json
    from pathlib import Path

    reports = sorted(Path("data/reports").glob("drift_*.json"), reverse=True)
    if not reports:
        return
    try:
        with open(reports[0]) as f:
            data = json.load(f)
        for feature, psi in data.get("psi_scores", {}).items():
            DRIFT_PSI.labels(feature=feature).set(float(psi))
    except Exception:
        log.debug("Drift JSON parse failed: %s", reports[0])


def main() -> None:
    start_http_server(METRICS_PORT)
    log.info("Metrics server started on :%d", METRICS_PORT)

    conn = psycopg.connect(POSTGRES_DSN, autocommit=True)

    while True:
        try:
            scrape_postgres(conn)
            scrape_mlflow()
            scrape_drift()
        except Exception:
            log.exception("Scrape cycle failed — reconnecting")
            try:
                conn.close()
            except Exception:
                pass
            conn = psycopg.connect(POSTGRES_DSN, autocommit=True)
        time.sleep(SCRAPE_INTERVAL)


if __name__ == "__main__":
    main()
