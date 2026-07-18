"""Dagster orchestration for the Binance anomaly detection pipeline."""
from __future__ import annotations

import logging
import os
import subprocess
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

import psycopg
from dagster import (
    AssetExecutionContext,
    Definitions,
    ScheduleDefinition,
    asset,
    define_asset_job,
    sensor,
    RunRequest,
    SkipReason,
)

log = logging.getLogger(__name__)

POSTGRES_DSN    = os.getenv("POSTGRES_DSN", "postgresql://anomaly:anomaly@postgres:5432/anomaly")
MLFLOW_URI      = os.getenv("MLFLOW_TRACKING_URI", "http://mlflow:5000")
REPORTS_PATH    = Path(os.getenv("REPORTS_PATH", "data/reports"))
MIN_SAMPLES     = int(os.getenv("TRAINING_MIN_SAMPLES", "500"))


# ---------------------------------------------------------------------------
# Assets
# ---------------------------------------------------------------------------

@asset(description="Train Isolation Forest on recent kline_features and register in MLflow.")
def train_anomaly_model(context: AssetExecutionContext) -> None:
    sys.path.insert(0, str(Path(__file__).parent.parent))
    from training.train_model import load_training_data, train, register, promote_latest
    import mlflow

    mlflow.set_tracking_uri(MLFLOW_URI)

    with psycopg.connect(POSTGRES_DSN) as conn:
        df = load_training_data(conn)

    context.log.info("Loaded %d kline records for training", len(df))

    if len(df) < MIN_SAMPLES:
        context.log.warning(
            "Only %d samples — need %d. Skipping. Let the producer run longer.",
            len(df), MIN_SAMPLES,
        )
        return

    pipeline, metrics = train(df)
    context.log.info("Training complete: %s", metrics)
    register(pipeline, metrics, df)
    promote_latest()
    context.add_output_metadata({"metrics": str(metrics)})


@asset(
    deps=[train_anomaly_model],
    description="Run Evidently PSI / KS / JS drift check on kline features.",
)
def run_drift_check(context: AssetExecutionContext) -> None:
    sys.path.insert(0, str(Path(__file__).parent.parent))
    from observability.drift_job import run_drift

    REPORTS_PATH.mkdir(parents=True, exist_ok=True)
    report_path = run_drift(POSTGRES_DSN, REPORTS_PATH)
    if report_path:
        context.log.info("Drift report saved: %s", report_path)
        context.add_output_metadata({"report": str(report_path)})
    else:
        context.log.warning("Drift check skipped — not enough data")


@asset(description="Submit the PyFlink anomaly detection job to the JobManager.")
def submit_flink_job(context: AssetExecutionContext) -> None:
    flink_job = str(Path(__file__).parent.parent / "streaming" / "flink_job.py")
    result = subprocess.run(
        ["python", flink_job],
        capture_output=True, text=True, timeout=30,
    )
    context.log.info("Flink submit stdout: %s", result.stdout[-2000:])
    if result.returncode != 0:
        context.log.error("Flink submit stderr: %s", result.stderr[-2000:])
        raise RuntimeError(f"Flink job submission failed (rc={result.returncode})")


@asset(description="Resolve anomaly alerts older than 1 hour automatically.")
def resolve_stale_alerts(context: AssetExecutionContext) -> None:
    with psycopg.connect(POSTGRES_DSN) as conn:
        cur = conn.execute(
            """
            UPDATE anomaly_alerts
            SET resolved = TRUE, resolved_at = NOW()
            WHERE resolved = FALSE
              AND triggered_at < NOW() - INTERVAL '1 hour'
            RETURNING alert_id
            """
        )
        rows = cur.fetchall()
        conn.commit()
    context.log.info("Resolved %d stale alerts", len(rows))
    context.add_output_metadata({"resolved_count": len(rows)})


# ---------------------------------------------------------------------------
# Jobs
# ---------------------------------------------------------------------------

training_job      = define_asset_job("training_job",      selection=[train_anomaly_model])
drift_job         = define_asset_job("drift_job",         selection=[run_drift_check])
resolve_job       = define_asset_job("resolve_alerts_job", selection=[resolve_stale_alerts])


# ---------------------------------------------------------------------------
# Schedules
# ---------------------------------------------------------------------------

training_schedule = ScheduleDefinition(
    job=training_job,
    cron_schedule="0 2 * * *",   # daily at 02:00 UTC
    name="daily_training",
)

drift_schedule = ScheduleDefinition(
    job=drift_job,
    cron_schedule="0 */2 * * *",  # every 2 hours
    name="drift_check_schedule",
)

resolve_schedule = ScheduleDefinition(
    job=resolve_job,
    cron_schedule="*/15 * * * *", # every 15 min
    name="resolve_stale_alerts_schedule",
)


# ---------------------------------------------------------------------------
# Sensor: auto-trigger retraining when drift score is high
# ---------------------------------------------------------------------------

@sensor(job=training_job, name="drift_triggered_retraining")
def drift_retrain_sensor(context):
    """Trigger retraining if latest drift report contains a PSI > 0.25."""
    reports = sorted(REPORTS_PATH.glob("drift_*.json"), reverse=True)
    if not reports:
        return SkipReason("No drift reports yet")

    import json
    with open(reports[0]) as f:
        report_data = json.load(f)

    max_psi = report_data.get("max_psi", 0.0)
    if max_psi > 0.25:
        return RunRequest(
            run_key=reports[0].stem,
            tags={"trigger": "drift", "max_psi": str(max_psi)},
        )
    return SkipReason(f"Max PSI {max_psi:.3f} below threshold 0.25")


# ---------------------------------------------------------------------------
# Definitions
# ---------------------------------------------------------------------------

defs = Definitions(
    assets=[train_anomaly_model, run_drift_check, submit_flink_job, resolve_stale_alerts],
    jobs=[training_job, drift_job, resolve_job],
    schedules=[training_schedule, drift_schedule, resolve_schedule],
    sensors=[drift_retrain_sensor],
)
