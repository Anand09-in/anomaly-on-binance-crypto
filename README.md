# Real-Time Streaming Anomaly Detection Platform  
**(Binance × Kafka × Flink × EKS × Terraform)**

A production-grade, cloud-native real-time anomaly detection system that ingests live cryptocurrency market data, processes it using distributed stream processing (PyFlink), and generates low-latency anomaly alerts.  
The system is fully containerized, deployed on AWS EKS, and monitored with Prometheus & Grafana.

---

## 🚀 Features

- Live crypto data ingestion from Binance WebSocket streams  
- Kafka-based high-throughput streaming pipeline  
- Distributed real-time processing using PyFlink  
- Windowed feature computation (10s, 1m) for volatility and statistical modeling  
- Real-time anomaly detection (Z-score, MAD)  
- Cloud-native deployment on AWS EKS via Flink Kubernetes Operator  
- Fault-tolerant state management using  S3 checkpoints  
- Infrastructure fully automated with Terraform  
- Centralized monitoring using Prometheus & Grafana
  
---

## 🧠 Core Components

### **1. Kafka Producer**
- Connects to Binance WebSocket  
- Streams normalized events into Kafka (`raw-trades`, `kline-10s`)  
- Exposes Prometheus metrics  

### **2. PyFlink Real-Time Processor**
- Consumes Kafka streams  
- Computes sliding/tumbling windows  
- Extracts features (VWAP, volatility, returns, volume spikes)  
- Detects anomalies using statistical methods  
- Publishes alerts to Kafka (`alerts`)  
- Writes historical aggregates to S3 (Parquet)  

### **3. AWS EKS + Flink Kubernetes Operator**
- Manages JobManager & TaskManagers  
- Supports autoscaling and rolling upgrades  
- Ensures high availability  

### **4. Infrastructure as Code (Terraform)**
- Provisions:  
  - VPC  
  - EKS cluster + Node groups  
  - S3 buckets  
  - IAM roles (IRSA)  
  - ECR repositories  

### **5. Monitoring**
- Prometheus scrapes metrics from Kafka, Flink, and producer  
- Grafana dashboards visualize throughput, latency, anomalies, state size, and checkpoint health  

---

## 🛠️ Tech Stack

| Category | Tools |
|---------|-------|
| Data Source | Binance WebSocket API |
| Ingestion | Kafka |
| Stream Processing | Flink (PyFlink) |
| Cloud Platform | AWS EKS, EC2, S3 |
| Infrastructure | Terraform |
| Containers | Docker |
| Monitoring | Prometheus, Grafana |




