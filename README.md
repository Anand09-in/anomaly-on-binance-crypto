# 🪙 Real-Time ML-Based Streaming Anomaly Detection Platform

**Binance × Kafka × Flink × Spark × AWS × Terraform**

A **production-grade, cloud-native streaming ML platform** that ingests live cryptocurrency market data from Binance, performs real-time feature extraction using distributed stream processing, and applies **machine learning–based anomaly detection** to identify abnormal market behavior with low latency.

The system is fully containerized, infrastructure-driven via Terraform, and designed with **modern MLOps principles** including model lifecycle management, artifact versioning, and observability.

---

## 🚀 Key Capabilities

* Live market data ingestion from Binance WebSocket streams
* High-throughput Kafka-based streaming backbone
* Real-time feature extraction with PyFlink (windowed aggregations)
* ML-based anomaly detection (beyond static thresholds)
* Offline / batch ML training using Spark
* Model tracking & lifecycle management with MLflow
* Cloud-native deployment on AWS (EKS + EC2)
* Fault-tolerant state and checkpoints backed by S3
* Centralized monitoring with Prometheus & Grafana
* Fully automated, reproducible infrastructure using Terraform

---

## 🧠 System Architecture

### **1. Streaming Data Ingestion (Kafka Producer)**

* Connects to Binance WebSocket APIs
* Streams normalized trade and aggregation events to Kafka
* Supports multiple symbols via configuration
* Exposes operational metrics for monitoring

**Kafka Topics**

* `raw-trades`
* `kline-10s`
* `kline-1m`
* `alerts`

---

### **2. Real-Time Feature Engineering (PyFlink)**

* Consumes Kafka streams
* Computes sliding and tumbling windows (10s, 1m)
* Generates real-time features such as:

  * Returns
  * Volatility
  * VWAP
  * Volume imbalance
  * Price momentum
* Persists aggregated features to S3 (Parquet)

---

### **3. ML-Based Anomaly Detection**

* Uses streaming features for **online anomaly scoring**
* Supports:

  * Feature-driven statistical models
  * ML-based detectors (Isolation Forest, clustering-based, probabilistic models)
* Separates **training (offline)** from **inference (streaming)**
* Publishes detected anomalies to Kafka (`alerts`)

---

### **4. Batch ML Training (Spark + MLflow)**

* Spark jobs read historical features from S3
* Train and evaluate anomaly detection models
* Log experiments, metrics, and artifacts to MLflow
* Store trained models and metadata in S3
* Enables model iteration without redeploying infrastructure

---

### **5. Cloud Infrastructure & Deployment**

* **Terraform-managed infrastructure**

  * VPC, Subnets, Security Groups
  * EKS cluster and node groups
  * EC2 (Kafka, supporting services)
  * S3 buckets (features, artifacts, checkpoints)
  * ECR repositories
* **Containerized services**

  * Kafka cluster
  * Binance producer
  * Flink jobs
  * MLflow server

---

## 🛠️ Tech Stack

| Layer             | Tools                  |
| ----------------- | ---------------------- |
| Data Source       | Binance WebSocket API  |
| Streaming         | Kafka                  |
| Stream Processing | Apache Flink (PyFlink) |
| Batch Processing  | Apache Spark           |
| ML Lifecycle      | MLflow                 |
| Storage           | Amazon S3              |
| Cloud             | AWS (EC2, EKS, IAM)    |
| Infrastructure    | Terraform              |
| Containers        | Docker                 |
| Monitoring        | Prometheus, Grafana    |
