# anomaly-on-binance

Real-time crypto anomaly detection pipeline. Streams live trade data from Binance, builds OHLCV kline windows, scores each window with Isolation Forest, and fires alerts on price spikes, volume surges, and model-detected pattern anomalies.

## Architecture

```
Binance WebSocket
      │
      ▼
Kafka Producer (aiokafka)
  raw-trades  ──────────────────────────────────────────┐
  kline-10s   ─────────────────────────────────────┐    │
  kline-1m                                         │    │
                                                   ▼    │
                                     PyFlink (1.18)     │
                                     feature compute     │
                                     + anomaly score     │
                                          │              │
                              ┌───────────┴──────────┐   │
                              ▼                      ▼   │
                         kline_features       anomaly_alerts
                              │  (Postgres)         │
                              └──────────┬──────────┘
                                         │
                    ┌────────────────────┼─────────────────────┐
                    ▼                    ▼                      ▼
              Dagster (1.7)       metrics_exporter       Streamlit (8501)
              - daily training    Prometheus (9090)
              - drift check 2h    Grafana (3001)
              - auto-retrain
```

## Stack

| Layer | Technology |
|---|---|
| Data source | Binance WebSocket (`trade` streams) |
| Message broker | Apache Kafka 3.8 (KRaft, no Zookeeper) |
| Stream processing | PyFlink 1.18 — event-time, keyed state, Postgres sink |
| ML model | Isolation Forest (scikit-learn) — rule-based fallback |
| Model registry | MLflow 2.12 |
| Orchestration | Dagster 1.7 — 3 schedules, drift sensor |
| Drift detection | Evidently — PSI / KS per feature, 2h cadence |
| Observability | Prometheus + Grafana (10 panels) |
| Dashboard | Streamlit — 5 tabs: klines, anomalies, velocity, alerts, drift |
| Infra | Terraform (single EC2 t3.medium + Docker Compose) |

## Kafka Topics

| Topic | Producer | Consumer |
|---|---|---|
| `raw-trades` | Binance WS producer | (archival) |
| `kline-10s` | producer aggregator | Flink job |
| `kline-1m` | producer aggregator | (future) |
| `anomaly-alerts` | Flink job | downstream consumers |

## Quick Start (local)

```bash
# 1. Clone and copy env
cp .env.example .env

# 2. Start the full stack
docker compose up -d

# 3. Wait ~60s, then create Kafka topics
docker compose exec kafka /opt/kafka/bin/kafka-topics.sh \
  --bootstrap-server localhost:9092 --create --if-not-exists \
  --topic raw-trades    --partitions 3 --replication-factor 1
docker compose exec kafka /opt/kafka/bin/kafka-topics.sh \
  --bootstrap-server localhost:9092 --create --if-not-exists \
  --topic kline-10s     --partitions 3 --replication-factor 1
docker compose exec kafka /opt/kafka/bin/kafka-topics.sh \
  --bootstrap-server localhost:9092 --create --if-not-exists \
  --topic kline-1m      --partitions 1 --replication-factor 1
docker compose exec kafka /opt/kafka/bin/kafka-topics.sh \
  --bootstrap-server localhost:9092 --create --if-not-exists \
  --topic anomaly-alerts --partitions 1 --replication-factor 1

# 4. Submit the Flink job
docker compose exec flink-jobmanager \
  python /opt/anomaly/streaming/flink_job.py

# 5. Wait for ~500 kline records, then train the model
docker compose exec dagster \
  python -m training.train_model
```

## Service URLs

| Service | URL | Credentials |
|---|---|---|
| Streamlit | http://localhost:8501 | — |
| Dagster | http://localhost:3000 | — |
| Grafana | http://localhost:3001 | admin / anomaly |
| MLflow | http://localhost:5000 | — |
| Flink UI | http://localhost:8081 | — |
| Kafka UI | http://localhost:8080 | — |
| Prometheus | http://localhost:9090 | — |

## Anomaly Types

| Type | Trigger |
|---|---|
| `price_spike` | `|price_change_pct|` > 2.0% in a 10s window |
| `volume_surge` | volume > 5× rolling 30-window average |
| `pattern_anomaly` | Isolation Forest decision score < −0.10 |

## Dagster Schedules

| Schedule | Cron | Job |
|---|---|---|
| `daily_training` | `0 2 * * *` | Retrain Isolation Forest |
| `drift_check_schedule` | `0 */2 * * *` | Evidently PSI/KS drift check |
| `resolve_stale_alerts_schedule` | `*/15 * * * *` | Auto-resolve alerts > 1h old |

The `drift_triggered_retraining` sensor fires an out-of-schedule retrain when any PSI score exceeds 0.25.

## Terraform Deploy (AWS)

```bash
cd infra
terraform init \
  -backend-config="bucket=<your-tfstate-bucket>" \
  -backend-config="key=anomaly/terraform.tfstate" \
  -backend-config="region=ap-south-1"

terraform apply \
  -var="ec2_key_name=<your-key-pair>" \
  -var="allowed_cidr=<your-ip>/32" \
  -var="github_repo=Anand09-in/anomaly-on-binance"
```

## Project Structure

```
.
├── Kafka/Producer/          # Binance WS → Kafka (aiokafka, asyncio)
│   └── src/
│       ├── binance_ws.py    # WebSocket client with reconnect backoff
│       ├── aggregator.py    # MultiWindowAggregator (10s + 1m OHLCV)
│       ├── kafka_producer.py
│       ├── main.py
│       ├── config.py        # pydantic Settings
│       └── metrics.py       # Prometheus counters/gauges
├── streaming/
│   └── flink_job.py         # PyFlink: parse → features → anomaly detect → Postgres
├── training/
│   └── train_model.py       # Isolation Forest + MLflow registration
├── orchestration/
│   └── definitions.py       # Dagster assets, schedules, drift sensor
├── observability/
│   ├── metrics_exporter.py  # Prometheus exporter (scrapes Postgres)
│   ├── drift_job.py         # Evidently PSI + HTML report
│   └── prometheus/
│       ├── prometheus.yml
│       └── alerts.yml
├── serving/
│   ├── streamlit_app.py     # 5-tab ops dashboard
│   └── grafana/
│       ├── datasource.yml
│       ├── dashboard.yml
│       └── anomaly_dashboard.json
├── migrations/
│   └── 001_init.sql         # kline_features + anomaly_alerts schema
├── infra/
│   ├── main.tf              # VPC + EC2 + SG
│   ├── variables.tf
│   └── outputs.tf
├── docker-compose.yml       # Full local stack (11 services)
├── Dockerfile.flink         # Flink 1.18 + PyFlink + Kafka connector JAR
└── setup.py
```
