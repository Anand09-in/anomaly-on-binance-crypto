"""
Train Isolation Forest on historical kline_features from Postgres.
Registers the model in MLflow under experiment 'binance-anomaly'.

Usage:
    python -m training.train_model
    # or from Dagster asset
"""
from __future__ import annotations

import logging
import os
from datetime import datetime, timedelta, timezone

import mlflow
import mlflow.sklearn
import numpy as np
import pandas as pd
import psycopg
from sklearn.ensemble import IsolationForest
from sklearn.preprocessing import StandardScaler
from sklearn.pipeline import Pipeline

log = logging.getLogger(__name__)

POSTGRES_DSN     = os.getenv("POSTGRES_DSN", "postgresql://anomaly:anomaly@postgres:5432/anomaly")
MLFLOW_URI       = os.getenv("MLFLOW_TRACKING_URI", "http://mlflow:5000")
EXPERIMENT_NAME  = os.getenv("MLFLOW_EXPERIMENT_NAME", "binance-anomaly")
LOOKBACK_DAYS    = int(os.getenv("TRAINING_LOOKBACK_DAYS", "7"))
MIN_SAMPLES      = int(os.getenv("TRAINING_MIN_SAMPLES", "500"))

# Isolation Forest hyperparams
IF_CONTAMINATION = float(os.getenv("IF_CONTAMINATION", "0.05"))
IF_N_ESTIMATORS  = int(os.getenv("IF_N_ESTIMATORS", "100"))
IF_MAX_SAMPLES   = os.getenv("IF_MAX_SAMPLES", "auto")
IF_RANDOM_STATE  = 42

FEATURE_COLS = ["price_change_pct", "price_range_pct", "volume_ratio"]


def load_training_data(conn: psycopg.Connection) -> pd.DataFrame:
    cutoff = datetime.now(tz=timezone.utc) - timedelta(days=LOOKBACK_DAYS)
    df = pd.read_sql(
        """
        SELECT
            symbol,
            window_start,
            price_change_pct,
            price_range_pct,
            volume,
            AVG(volume) OVER (
                PARTITION BY symbol
                ORDER BY window_start
                ROWS BETWEEN 29 PRECEDING AND 1 PRECEDING
            ) AS rolling_avg_volume
        FROM kline_features
        WHERE window_start > %s
          AND price_change_pct IS NOT NULL
        ORDER BY window_start
        """,
        conn,
        params=(cutoff,),
    )
    # volume_ratio: current vs rolling avg (fallback to 1.0 if no history yet)
    df["volume_ratio"] = df["volume"] / df["rolling_avg_volume"].replace(0, np.nan)
    df["volume_ratio"] = df["volume_ratio"].fillna(1.0).clip(0, 20)
    df = df.dropna(subset=FEATURE_COLS)
    return df


def train(df: pd.DataFrame) -> tuple[Pipeline, dict]:
    X = df[FEATURE_COLS].values

    pipeline = Pipeline([
        ("scaler", StandardScaler()),
        ("iso_forest", IsolationForest(
            n_estimators=IF_N_ESTIMATORS,
            contamination=IF_CONTAMINATION,
            max_samples=IF_MAX_SAMPLES,
            random_state=IF_RANDOM_STATE,
            n_jobs=-1,
        )),
    ])
    pipeline.fit(X)

    scores = pipeline.decision_function(X)
    preds  = pipeline.predict(X)
    n_anomalies = int((preds == -1).sum())

    metrics = {
        "n_samples":      len(df),
        "n_anomalies":    n_anomalies,
        "anomaly_rate":   n_anomalies / len(df),
        "score_mean":     float(scores.mean()),
        "score_std":      float(scores.std()),
        "symbols":        df["symbol"].nunique(),
        "lookback_days":  LOOKBACK_DAYS,
    }
    return pipeline, metrics


def register(pipeline: Pipeline, metrics: dict, df: pd.DataFrame) -> str:
    mlflow.set_tracking_uri(MLFLOW_URI)
    mlflow.set_experiment(EXPERIMENT_NAME)

    with mlflow.start_run(run_name=f"iso_forest_{datetime.now(tz=timezone.utc).strftime('%Y%m%d_%H%M')}") as run:
        mlflow.log_params({
            "n_estimators":   IF_N_ESTIMATORS,
            "contamination":  IF_CONTAMINATION,
            "max_samples":    IF_MAX_SAMPLES,
            "lookback_days":  LOOKBACK_DAYS,
            "features":       ",".join(FEATURE_COLS),
        })
        mlflow.log_metrics(metrics)

        # Log sample of training data as artifact
        sample_path = "/tmp/training_sample.csv"
        df.head(200).to_csv(sample_path, index=False)
        mlflow.log_artifact(sample_path, "data")

        model_info = mlflow.sklearn.log_model(
            pipeline,
            "model",
            registered_model_name="binance-isolation-forest",
        )
        run_id = run.info.run_id

    log.info(
        "Registered model — run_id=%s n_samples=%d anomaly_rate=%.2f%%",
        run_id, metrics["n_samples"], metrics["anomaly_rate"] * 100,
    )
    return run_id


def promote_latest():
    """Promote the most recent registered version to Production."""
    mlflow.set_tracking_uri(MLFLOW_URI)
    client = mlflow.MlflowClient()
    versions = client.get_latest_versions("binance-isolation-forest", stages=["None"])
    if not versions:
        log.warning("No model version to promote")
        return
    latest = max(versions, key=lambda v: int(v.version))
    client.transition_model_version_stage(
        name="binance-isolation-forest",
        version=latest.version,
        stage="Production",
    )
    log.info("Promoted version %s to Production", latest.version)


def main():
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s - %(message)s")

    with psycopg.connect(POSTGRES_DSN) as conn:
        log.info("Loading training data (last %d days)…", LOOKBACK_DAYS)
        df = load_training_data(conn)

    log.info("Loaded %d kline records across %d symbols", len(df), df["symbol"].nunique())

    if len(df) < MIN_SAMPLES:
        log.warning(
            "Only %d samples available (need %d). Skipping training — run the producer first.",
            len(df), MIN_SAMPLES,
        )
        return

    pipeline, metrics = train(df)
    log.info("Training metrics: %s", metrics)

    register(pipeline, metrics, df)
    promote_latest()


if __name__ == "__main__":
    main()
