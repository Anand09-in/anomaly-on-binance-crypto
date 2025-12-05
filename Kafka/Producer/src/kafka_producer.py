import asyncio
import json
import logging
from typing import Any, Dict, Optional
from aiokafka import AIOKafkaProducer
from config import Settings

settings = Settings()
log = logging.getLogger(__name__)


def _serialize(value: Dict[str, Any]) -> bytes:
    # Lightweight serializer; you can replace with avro/protobuf later
    return json.dumps(value, default=str).encode("utf-8")


class KafkaWriter:
    def __init__(self):
        self._producer: Optional[AIOKafkaProducer] = None
        self._started = False

    async def start(self):
        if self._started:
            return
        kws = {
            "bootstrap_servers": settings.KAFKA_BOOTSTRAP_SERVERS.split(","),
            "client_id": settings.PRODUCER_CLIENT_ID,
            "linger_ms": settings.PRODUCER_LINGER_MS,
        }
        if settings.PRODUCER_COMPRESSION_TYPE:
            kws["compression_type"] = settings.PRODUCER_COMPRESSION_TYPE
        self._producer = AIOKafkaProducer(**kws)
        await self._producer.start()
        self._started = True
        log.info("Kafka producer started with servers=%s", settings.KAFKA_BOOTSTRAP_SERVERS)

    async def stop(self):
        if self._producer:
            await self._producer.stop()
            log.info("Kafka producer stopped")

    async def send(self, topic: str, value: Dict[str, Any], key: Optional[bytes] = None):
        payload = _serialize(value)
        for attempt in range(settings.PRODUCER_MAX_RETRIES):
            try:
                await self._producer.send_and_wait(topic, payload, key=key)
                return
            except Exception:
                log.exception("Failed to send to Kafka topic=%s attempt=%d", topic, attempt + 1)
                await asyncio.sleep(min(2 ** attempt, 10))
        log.error("Dropping message to topic=%s after %d retries", topic, settings.PRODUCER_MAX_RETRIES)

    async def send_metrics(self, metric_type: str, payload: Dict[str, Any]):
        """
        Optionally publish metrics to a configured Kafka topic (KAFKA_METRICS_TOPIC).
        message: {"type": metric_type, "payload": {...}, "ts": epoch_ms}
        """
        if not settings.KAFKA_METRICS_TOPIC:
            return
        msg = {"type": metric_type, "payload": payload, "ts": int(asyncio.get_event_loop().time() * 1000)}
        await self.send(settings.KAFKA_METRICS_TOPIC, msg)
