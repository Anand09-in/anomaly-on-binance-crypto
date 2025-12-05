from typing import List, Optional
from pydantic import BaseSettings, validator


class Settings(BaseSettings):
    # Binance
    BINANCE_WS_BASE: str = "wss://stream.binance.com:9443/stream"
    SYMBOLS: str = "btcusdt"  # comma-separated list, e.g. "btcusdt,ethusdt"
    WS_STREAM_TYPE: str = "trade"  # trade | aggTrade | miniTicker

    # Kafka
    KAFKA_BOOTSTRAP_SERVERS: str = "kafka:9092"
    KAFKA_RAW_TOPIC: str = "raw-trades"
    KAFKA_KLINE_10S_TOPIC: str = "kline-10s"
    KAFKA_KLINE_1M_TOPIC: str = "kline-1m"
    KAFKA_METRICS_TOPIC: Optional[str] = None  # optional topic to push metrics to

    PRODUCER_CLIENT_ID: str = "binance-producer"
    PRODUCER_MAX_RETRIES: int = 5
    PRODUCER_LINGER_MS: int = 50
    PRODUCER_COMPRESSION_TYPE: Optional[str] = None  # e.g. 'lz4', 'snappy', 'gzip'

    # Aggregation windows
    AGG_WINDOW_SECONDS_10S: int = 10
    AGG_WINDOW_SECONDS_1M: int = 60

    # Prometheus
    PROMETHEUS_PORT: int = 8000
    METRICS_PUSH_TO_KAFKA: bool = False

    # Logging / runtime
    LOG_LEVEL: str = "INFO"
    MAX_WS_RECONNECT_BACKOFF: int = 60
    DEBUG: bool = False

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"

    @property
    def symbol_list(self) -> List[str]:
        return [s.strip().lower() for s in self.SYMBOLS.split(",") if s.strip()]

    @validator("WS_STREAM_TYPE")
    def validate_stream_type(cls, v: str):
        allowed = {"trade", "aggTrade", "miniTicker"}
        if v not in allowed:
            raise ValueError(f"WS_STREAM_TYPE must be one of {allowed}")
        return v
