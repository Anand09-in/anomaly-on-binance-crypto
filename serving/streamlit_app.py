"""
Binance Anomaly Detection — Streamlit ops dashboard.

Reads from Postgres kline_features + anomaly_alerts tables.
Run:
    streamlit run serving/streamlit_app.py
"""
from __future__ import annotations

import os
from datetime import UTC, datetime
from pathlib import Path

import pandas as pd
import streamlit as st

st.set_page_config(
    page_title="Binance Anomaly Monitor",
    page_icon="🔍",
    layout="wide",
    initial_sidebar_state="expanded",
)

POSTGRES_DSN = os.getenv(
    "POSTGRES_DSN",
    "postgresql://anomaly:anomaly@localhost:5432/anomaly",
)
REPORTS_PATH = Path(os.getenv("REPORTS_PATH", "data/reports"))
REFRESH_S    = int(os.getenv("DASHBOARD_REFRESH_S", "15"))
ALERT_WINDOW = int(os.getenv("ALERT_WINDOW_MIN", "60"))


# ---------------------------------------------------------------------------
# DB
# ---------------------------------------------------------------------------
@st.cache_resource
def get_conn():
    import psycopg
    return psycopg.connect(POSTGRES_DSN, autocommit=True)


def query(sql: str, params: tuple = ()) -> pd.DataFrame:
    try:
        return pd.read_sql(sql, get_conn(), params=params)
    except Exception as e:
        st.error(f"DB error: {e}")
        return pd.DataFrame()


# ---------------------------------------------------------------------------
# Fetchers
# ---------------------------------------------------------------------------

def fetch_freshness() -> dict:
    df = query("SELECT symbol, MAX(window_end) AS latest FROM kline_features GROUP BY symbol")
    if df.empty:
        return {"lag_s": None, "status": "no_data", "symbols": []}
    df["lag_s"] = (datetime.now(tz=UTC) - pd.to_datetime(df["latest"], utc=True)).dt.total_seconds()
    worst = float(df["lag_s"].max())
    status = "healthy" if worst < 30 else "stale" if worst < 120 else "down"
    return {"lag_s": worst, "status": status, "by_symbol": df}


def fetch_alert_counts() -> dict:
    df = query(
        """
        SELECT alert_type, COUNT(*) AS cnt
        FROM anomaly_alerts
        WHERE resolved = FALSE
        GROUP BY alert_type
        """
    )
    if df.empty:
        return {"price_spike": 0, "volume_surge": 0, "pattern_anomaly": 0, "total": 0}
    counts = dict(zip(df["alert_type"], df["cnt"].astype(int), strict=True))
    counts["total"] = sum(counts.values())
    return counts


def fetch_recent_klines(symbol: str, limit: int = 60) -> pd.DataFrame:
    return query(
        """
        SELECT window_start, window_end, open_price, high_price, low_price, close_price,
               volume, trade_count, price_change_pct, price_range_pct
        FROM kline_features
        WHERE symbol = %s
        ORDER BY window_start DESC
        LIMIT %s
        """,
        (symbol, limit),
    )


def fetch_active_anomalies() -> pd.DataFrame:
    return query(
        """
        SELECT a.symbol, a.alert_type, a.metric_value, a.threshold,
               a.anomaly_score, a.triggered_at,
               f.close_price, f.price_change_pct, f.volume
        FROM anomaly_alerts a
        LEFT JOIN LATERAL (
            SELECT close_price, price_change_pct, volume
            FROM kline_features f2
            WHERE f2.symbol = a.symbol AND f2.window_start = a.window_start
        ) f ON true
        WHERE a.resolved = FALSE
        ORDER BY a.triggered_at DESC
        LIMIT 100
        """
    )


def fetch_anomaly_history() -> pd.DataFrame:
    return query(
        f"""
        SELECT DATE_TRUNC('hour', triggered_at) AS hour,
               symbol, alert_type, COUNT(*) AS cnt
        FROM anomaly_alerts
        WHERE triggered_at > NOW() - INTERVAL '{ALERT_WINDOW} minutes'
        GROUP BY 1, 2, 3
        ORDER BY 1 DESC
        """
    )


def fetch_symbol_velocity() -> pd.DataFrame:
    return query(
        """
        SELECT symbol,
               ROUND(AVG(price_change_pct)::numeric, 4) AS avg_price_change,
               ROUND(AVG(price_range_pct)::numeric, 4)  AS avg_range,
               ROUND(AVG(volume)::numeric, 4)            AS avg_volume,
               COUNT(*)                                  AS klines
        FROM kline_features
        WHERE window_end > NOW() - INTERVAL '10 minutes'
        GROUP BY symbol
        ORDER BY avg_volume DESC
        """
    )


def fetch_recent_alerts_log() -> pd.DataFrame:
    return query(
        """
        SELECT alert_type, symbol, metric_value, threshold,
               anomaly_score, resolved, triggered_at
        FROM anomaly_alerts
        ORDER BY triggered_at DESC
        LIMIT 200
        """
    )


def load_latest_drift_report() -> Path | None:
    files = sorted(REPORTS_PATH.glob("drift_*.html"), reverse=True)
    return files[0] if files else None


# ---------------------------------------------------------------------------
# UI helpers
# ---------------------------------------------------------------------------
STATUS_MAP = {
    "healthy": ("🟢", "Healthy"),
    "stale":   ("🟡", "Stale"),
    "down":    ("🔴", "Down"),
    "no_data": ("⚫", "No data"),
}


def _fmt_lag(lag_s: float | None) -> str:
    if lag_s is None:
        return "—"
    return f"{lag_s:.0f}s ago" if lag_s < 60 else f"{lag_s / 60:.1f}m ago"


def _colour_alert_type(val: str) -> str:
    return {
        "price_spike":    "background-color:#ffcccc",
        "volume_surge":   "background-color:#fff3cc",
        "pattern_anomaly":"background-color:#e8ccff",
    }.get(val, "")


# ---------------------------------------------------------------------------
# Sidebar
# ---------------------------------------------------------------------------

def render_sidebar() -> str:
    st.sidebar.header("Controls")
    symbols_df = query("SELECT DISTINCT symbol FROM kline_features ORDER BY symbol")
    symbols = symbols_df["symbol"].tolist() if not symbols_df.empty else ["btcusdt"]
    symbol = st.sidebar.selectbox("Symbol", symbols, index=0)
    st.sidebar.markdown("---")
    st.sidebar.markdown(
        f"**Alert window:** last {ALERT_WINDOW} min  \n"
        f"**Auto-refresh:** every {REFRESH_S}s"
    )
    st.sidebar.markdown("---")
    st.sidebar.caption("PSI thresholds")
    st.sidebar.markdown("🟢 < 0.10 stable  \n🟡 0.10–0.25 moderate  \n🔴 > 0.25 drift")
    return symbol


# ---------------------------------------------------------------------------
# Panels
# ---------------------------------------------------------------------------

def render_header(freshness: dict, counts: dict) -> None:
    icon, label = STATUS_MAP.get(freshness["status"], ("⚫", "Unknown"))
    c1, c2, c3, c4, c5 = st.columns(5)
    c1.metric("Pipeline",       f"{icon} {label}")
    c2.metric("Worst Lag",      _fmt_lag(freshness.get("lag_s")))
    c3.metric("Active Alerts",  counts["total"])
    c4.metric("Price Spikes",   counts.get("price_spike", 0))
    c5.metric("Volume Surges",  counts.get("volume_surge", 0))


def render_klines(symbol: str) -> None:
    df = fetch_recent_klines(symbol)
    if df.empty:
        st.info(f"No kline data for {symbol.upper()} yet — producer may still be warming up.")
        return

    df = df.sort_values("window_start")
    st.markdown(f"**{symbol.upper()} — last {len(df)} windows (10s each)**")

    col1, col2 = st.columns(2)
    with col1:
        st.markdown("Close price")
        st.line_chart(df.set_index("window_start")["close_price"], height=200, color="#1d4ed8")
    with col2:
        st.markdown("Price change %")
        st.bar_chart(df.set_index("window_start")["price_change_pct"], height=200, color="#e63946")

    st.markdown("Volume (qty)")
    st.bar_chart(df.set_index("window_start")["volume"], height=160, color="#2a9d8f")

    with st.expander("Raw kline table"):
        st.dataframe(
            df[["window_start", "open_price", "high_price", "low_price", "close_price",
                "volume", "trade_count", "price_change_pct", "price_range_pct"]]
            .rename(columns={
                "window_start": "Time", "open_price": "Open", "high_price": "High",
                "low_price": "Low", "close_price": "Close", "volume": "Volume",
                "trade_count": "Trades", "price_change_pct": "Chg%", "price_range_pct": "Range%",
            }),
            use_container_width=True,
            hide_index=True,
        )


def render_anomalies() -> None:
    df = fetch_active_anomalies()
    if df.empty:
        st.success("No active anomalies. All symbols within normal range.")
        return

    st.caption(f"{len(df)} active anomaly alert(s)")

    by_type = df["alert_type"].value_counts()
    st.bar_chart(by_type, height=160, color="#e76f51")

    st.dataframe(
        df.style.map(_colour_alert_type, subset=["alert_type"]),
        use_container_width=True,
        hide_index=True,
    )


def render_velocity() -> None:
    df = fetch_symbol_velocity()
    if df.empty:
        st.info("No recent kline data in the last 10 minutes.")
        return

    col1, col2 = st.columns(2)
    with col1:
        st.markdown("**Average volume (last 10 min)**")
        st.bar_chart(df.set_index("symbol")["avg_volume"], height=200, color="#2a9d8f")
    with col2:
        st.markdown("**Average price change % (last 10 min)**")
        st.bar_chart(df.set_index("symbol")["avg_price_change"], height=200, color="#e63946")

    st.dataframe(
        df.rename(columns={
            "symbol": "Symbol", "avg_price_change": "Avg Chg%",
            "avg_range": "Avg Range%", "avg_volume": "Avg Volume", "klines": "Klines",
        }),
        use_container_width=True,
        hide_index=True,
    )


def render_alerts_tab() -> None:
    df = fetch_recent_alerts_log()
    if df.empty:
        st.info("No alerts yet.")
        return

    log_df = df.rename(columns={
        "alert_type": "Type", "symbol": "Symbol",
        "metric_value": "Value", "threshold": "Threshold",
        "anomaly_score": "IF Score", "resolved": "Resolved", "triggered_at": "Time",
    })
    st.dataframe(log_df, use_container_width=True, hide_index=True)

    hist = fetch_anomaly_history()
    if not hist.empty:
        st.markdown("**Alert count by type (last hour)**")
        pivot = hist.pivot_table(index="hour", columns="alert_type", values="cnt", aggfunc="sum").fillna(0)
        st.bar_chart(pivot, height=200)


def render_drift() -> None:
    report = load_latest_drift_report()

    col1, col2, col3 = st.columns(3)
    col1.markdown("**PSI < 0.10**  \n🟢 Stable")
    col2.markdown("**PSI 0.10–0.25**  \n🟡 Moderate shift")
    col3.markdown("**PSI > 0.25**  \n🔴 Significant — retrain triggered")

    st.divider()

    if report:
        st.success(f"Latest report: `{report.name}`")
        try:
            with open(report, "rb") as f:
                st.download_button(
                    "Download Evidently report (HTML)",
                    data=f,
                    file_name=report.name,
                    mime="text/html",
                )
        except OSError:
            pass
        all_reports = sorted(REPORTS_PATH.glob("drift_*.html"), reverse=True)
        if len(all_reports) > 1:
            with st.expander(f"All reports ({len(all_reports)})"):
                for r in all_reports:
                    st.caption(str(r))
    else:
        st.warning(
            "No drift reports yet.  \n"
            "Run: `python -m observability.drift_job`  \n"
            "Or wait for the Dagster `drift_check_schedule` (every 2h)."
        )


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main() -> None:
    st.markdown(
        f"<meta http-equiv='refresh' content='{REFRESH_S}'>",
        unsafe_allow_html=True,
    )

    symbol = render_sidebar()

    st.title("🔍 Binance Anomaly Monitor")
    st.caption(
        f"Last render: {datetime.now(tz=UTC).strftime('%H:%M:%S UTC')} · "
        f"auto-refreshes every {REFRESH_S}s"
    )

    freshness = fetch_freshness()
    counts    = fetch_alert_counts()
    render_header(freshness, counts)

    st.divider()

    tabs = st.tabs([
        "📈 Kline Stream",
        "🚨 Active Anomalies",
        "⚡ Symbol Velocity",
        "📋 Alert Log",
        "📊 Drift",
    ])

    with tabs[0]:
        st.subheader(f"{symbol.upper()} — live kline stream")
        render_klines(symbol)

    with tabs[1]:
        st.subheader("Active anomaly alerts")
        render_anomalies()

    with tabs[2]:
        st.subheader("Symbol velocity (last 10 min)")
        render_velocity()

    with tabs[3]:
        st.subheader("Full alert log")
        render_alerts_tab()

    with tabs[4]:
        st.subheader("Feature drift — Evidently reports")
        render_drift()


if __name__ == "__main__":
    main()
