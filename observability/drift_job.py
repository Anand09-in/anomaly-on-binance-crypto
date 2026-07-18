"""
Evidently drift detection on kline_features.

Compares the most recent CURRENT_HOURS of kline data against the
previous REFERENCE_HOURS as a reference window.
Writes an HTML report and a JSON summary to REPORTS_PATH.

Run:
    python -m observability.drift_job
"""
from __future__ import annotations

import json
import logging
import os
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pandas as pd
import psycopg

log = logging.getLogger(__name__)

POSTGRES_DSN     = os.getenv("POSTGRES_DSN", "postgresql://anomaly:anomaly@postgres:5432/anomaly")
REPORTS_PATH     = Path(os.getenv("REPORTS_PATH", "data/reports"))
REFERENCE_HOURS  = int(os.getenv("DRIFT_REFERENCE_HOURS", "24"))
CURRENT_HOURS    = int(os.getenv("DRIFT_CURRENT_HOURS", "2"))
MIN_ROWS         = int(os.getenv("DRIFT_MIN_ROWS", "100"))

FEATURE_COLS = ["price_change_pct", "price_range_pct", "buy_pressure", "volume"]


def load_windows(conn: psycopg.Connection) -> tuple[pd.DataFrame, pd.DataFrame]:
    now = datetime.now(tz=timezone.utc)
    current_start   = now - timedelta(hours=CURRENT_HOURS)
    reference_start = current_start - timedelta(hours=REFERENCE_HOURS)

    current = pd.read_sql(
        "SELECT * FROM kline_features WHERE window_start BETWEEN %s AND %s",
        conn, params=(current_start, now),
    )
    reference = pd.read_sql(
        "SELECT * FROM kline_features WHERE window_start BETWEEN %s AND %s",
        conn, params=(reference_start, current_start),
    )
    return reference, current


def compute_psi(reference: pd.Series, current: pd.Series, bins: int = 10) -> float:
    import numpy as np
    combined = pd.concat([reference, current])
    breakpoints = np.linspace(combined.min(), combined.max(), bins + 1)
    ref_pcts = np.histogram(reference, bins=breakpoints)[0] / len(reference)
    cur_pcts = np.histogram(current, bins=breakpoints)[0] / len(current)
    # Avoid log(0)
    ref_pcts = np.where(ref_pcts == 0, 1e-6, ref_pcts)
    cur_pcts = np.where(cur_pcts == 0, 1e-6, cur_pcts)
    psi = np.sum((cur_pcts - ref_pcts) * np.log(cur_pcts / ref_pcts))
    return float(psi)


def run_drift(dsn: str, reports_path: Path) -> Path | None:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s - %(message)s")

    with psycopg.connect(dsn) as conn:
        reference, current = load_windows(conn)

    if len(reference) < MIN_ROWS or len(current) < MIN_ROWS:
        log.warning(
            "Insufficient data for drift: reference=%d current=%d (need %d each)",
            len(reference), len(current), MIN_ROWS,
        )
        return None

    log.info("Reference=%d rows  Current=%d rows", len(reference), len(current))

    # PSI per feature
    psi_scores: dict[str, float] = {}
    for col in FEATURE_COLS:
        if col in reference.columns and col in current.columns:
            psi_scores[col] = compute_psi(reference[col].dropna(), current[col].dropna())

    max_psi   = max(psi_scores.values(), default=0.0)
    drift_detected = max_psi > 0.25

    log.info("PSI scores: %s  (max=%.3f, drift=%s)", psi_scores, max_psi, drift_detected)

    # Evidently HTML report
    timestamp  = datetime.now(tz=timezone.utc).strftime("%Y%m%d_%H%M")
    html_path  = reports_path / f"drift_{timestamp}.html"
    json_path  = reports_path / f"drift_{timestamp}.json"

    try:
        from evidently import ColumnMapping
        from evidently.report import Report
        from evidently.metric_preset import DataDriftPreset

        col_mapping = ColumnMapping(
            numerical_features=[c for c in FEATURE_COLS if c in reference.columns],
        )
        report = Report(metrics=[DataDriftPreset()])
        report.run(
            reference_data=reference[FEATURE_COLS].dropna(),
            current_data=current[FEATURE_COLS].dropna(),
            column_mapping=col_mapping,
        )
        report.save_html(str(html_path))
        log.info("HTML report → %s", html_path)
    except Exception:
        log.exception("Evidently report generation failed; saving PSI-only JSON")

    # JSON summary (always written — used by metrics_exporter and drift sensor)
    summary = {
        "timestamp":      timestamp,
        "reference_rows": len(reference),
        "current_rows":   len(current),
        "psi_scores":     psi_scores,
        "max_psi":        max_psi,
        "drift_detected": drift_detected,
    }
    with open(json_path, "w") as f:
        json.dump(summary, f, indent=2)
    log.info("JSON summary → %s", json_path)

    return html_path if html_path.exists() else json_path


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s - %(message)s")
    REPORTS_PATH.mkdir(parents=True, exist_ok=True)
    run_drift(POSTGRES_DSN, REPORTS_PATH)


if __name__ == "__main__":
    main()
