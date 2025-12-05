import logging
from prometheus_client import Counter, start_http_server, Gauge
from .config import Settings

settings = Settings()
log = logging.getLogger(__name__)

# Counters
MSG_RECEIVED = Counter("producer_messages_received_total", "Messages received from Binance", ["symbol"])
MSG_PRODUCED = Counter("producer_messages_produced_total", "Messages produced to Kafka", ["topic", "symbol"])
MSG_PRODUCER_ERRORS = Counter("producer_errors_total", "Producer errors", ["stage"])

# Gauges
CONNECTED_WS = Gauge("producer_ws_connections", "Number of active WS connections")

def start_metrics_server():
    try:
        start_http_server(settings.PROMETHEUS_PORT)
        log.info("Prometheus metrics server started on port %d", settings.PROMETHEUS_PORT)
    except Exception:
        log.exception("Failed to start Prometheus metrics server")
