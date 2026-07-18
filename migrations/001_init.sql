-- Anomaly-on-Binance — initial schema

CREATE TABLE IF NOT EXISTS kline_features (
    id            BIGSERIAL PRIMARY KEY,
    symbol        VARCHAR(20)   NOT NULL,
    window_start  TIMESTAMPTZ   NOT NULL,
    window_end    TIMESTAMPTZ   NOT NULL,
    open_price    DOUBLE PRECISION NOT NULL,
    high_price    DOUBLE PRECISION NOT NULL,
    low_price     DOUBLE PRECISION NOT NULL,
    close_price   DOUBLE PRECISION NOT NULL,
    volume        DOUBLE PRECISION NOT NULL,
    trade_count   INTEGER       NOT NULL,
    -- derived features (computed by Flink)
    price_change_pct  DOUBLE PRECISION,
    price_range_pct   DOUBLE PRECISION,
    buy_pressure      DOUBLE PRECISION,
    updated_at    TIMESTAMPTZ   DEFAULT NOW(),
    UNIQUE (symbol, window_start)
);

CREATE INDEX IF NOT EXISTS idx_kf_symbol_time
    ON kline_features (symbol, window_start DESC);

CREATE TABLE IF NOT EXISTS anomaly_alerts (
    alert_id      BIGSERIAL PRIMARY KEY,
    symbol        VARCHAR(20)   NOT NULL,
    window_start  TIMESTAMPTZ   NOT NULL,
    triggered_at  TIMESTAMPTZ   DEFAULT NOW(),
    alert_type    VARCHAR(50)   NOT NULL,   -- price_spike | volume_surge | pattern_anomaly
    metric_value  DOUBLE PRECISION,
    threshold     DOUBLE PRECISION,
    anomaly_score DOUBLE PRECISION,         -- Isolation Forest score (lower = more anomalous)
    resolved      BOOLEAN       DEFAULT FALSE,
    resolved_at   TIMESTAMPTZ
);

CREATE INDEX IF NOT EXISTS idx_aa_symbol_time
    ON anomaly_alerts (symbol, triggered_at DESC);
CREATE INDEX IF NOT EXISTS idx_aa_unresolved
    ON anomaly_alerts (resolved) WHERE resolved = FALSE;
