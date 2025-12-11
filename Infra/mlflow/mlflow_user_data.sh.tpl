#!/usr/bin/env bash
set -eux

# Install docker & docker-compose
apt-get update -y
apt-get install -y docker.io docker-compose python3-pip jq
systemctl enable --now docker

# Install awscli
pip3 install awscli

# Get DB secrets from Secrets Manager
DB_SECRET_JSON=$(aws secretsmanager get-secret-value --secret-id "${DB_SECRET_ARN}" --region ${REGION} --query SecretString --output text)
DB_USERNAME=$(echo "$DB_SECRET_JSON" | jq -r .username)
DB_PASSWORD=$(echo "$DB_SECRET_JSON" | jq -r .password)
DB_HOST=$(echo "$DB_SECRET_JSON" | jq -r .host)
DB_PORT=$(echo "$DB_SECRET_JSON" | jq -r .port)
DB_NAME=$(echo "$DB_SECRET_JSON" | jq -r .dbname)

# Create docker-compose file for MLflow + nginx
cat > /home/ubuntu/docker-compose-mlflow.yml <<EOF
version: '3.8'
services:
  mlflow:
    image: mlfloworg/mlflow:2.3.1
    environment:
      - MLFLOW_TRACKING_URI=http://0.0.0.0:5000
      - AWS_REGION=${REGION}
    command: mlflow server --backend-store-uri postgresql://${DB_USERNAME}:${DB_PASSWORD}@${DB_HOST}:${DB_PORT}/${DB_NAME} --default-artifact-root s3://${S3_BUCKET} --host 0.0.0.0 --port 5000
    ports:
      - "5000:5000"
    restart: unless-stopped
  nginx:
    image: nginx:stable
    ports:
      - "80:80"
    volumes:
      - ./nginx.conf:/etc/nginx/nginx.conf:ro
    depends_on:
      - mlflow
EOF

# create minimal nginx config
cat > /home/ubuntu/nginx.conf <<'NGINX'
events {}
http {
  server {
    listen 80;
    location / {
      proxy_pass http://localhost:5000/;
      proxy_set_header Host $host;
      proxy_set_header X-Real-IP $remote_addr;
    }
  }
}
NGINX

chown ubuntu:ubuntu /home/ubuntu/docker-compose-mlflow.yml /home/ubuntu/nginx.conf

# Start MLflow
cd /home/ubuntu
docker compose -f docker-compose-mlflow.yml up -d

# Ensure docker user permissions
usermod -aG docker ubuntu
