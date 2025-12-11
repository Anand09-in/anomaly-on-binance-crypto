#!/usr/bin/env bash
set -euo pipefail
export DEBIAN_FRONTEND=noninteractive

LOG() { echo "[$(date -u +'%Y-%m-%dT%H:%M:%SZ')] $*"; }

# ---- Configurable vars ----
REPO_DIR="$(dirname "$(realpath "$0")")"   # script location => repo root if placed at repo root
echo "Repository directory: ${REPO_DIR}"
COMPOSE_CANDIDATES=(
  "${REPO_DIR}/docker-compose.yaml"
  "${REPO_DIR}/kafka/docker-compose.yaml"
  "${REPO_DIR}/Infra/kafka/docker-compose.yaml"
)

ENV_FILE="${REPO_DIR}/.env"

# ---- Helper: install apt package if missing ----
install_pkg() {
  PKG="$1"
  if ! dpkg -s "$PKG" >/dev/null 2>&1; then
    LOG "Installing package: $PKG"
    apt-get install -y "$PKG"
  else
    LOG "Package $PKG already installed"
  fi
}

LOG "Starting kafka_install.sh from ${REPO_DIR}"

# ---- 1) Ensure required base packages for install ----
apt-get update -y
install_pkg "ca-certificates"
install_pkg "curl"
install_pkg "gnupg"
install_pkg "lsb-release"

# ---- 2) Install Docker (official repo) if not installed ----
if ! command -v docker >/dev/null 2>&1; then
  LOG "Docker not found — installing"
  mkdir -p /etc/apt/keyrings
  curl -fsSL https://download.docker.com/linux/ubuntu/gpg | gpg --dearmor -o /etc/apt/keyrings/docker.gpg
  echo "deb [arch=$(dpkg --print-architecture) signed-by=/etc/apt/keyrings/docker.gpg] https://download.docker.com/linux/ubuntu $(lsb_release -cs) stable" \
    | tee /etc/apt/sources.list.d/docker.list > /dev/null
  apt-get update -y
  apt-get install -y docker-ce docker-ce-cli containerd.io docker-compose-plugin
else
  LOG "Docker command exists; skipping Docker install"
fi

# ---- 3) Ensure docker daemon is running ----
LOG "Ensuring docker daemon is running"
systemctl enable docker || true
systemctl start docker || true

# wait for docker to be responsive
for i in $(seq 1 30); do
  if docker info >/dev/null 2>&1; then
    LOG "Docker is ready"
    break
  fi
  LOG "Waiting for docker... ($i/30)"
  sleep 1
  if [ "$i" -eq 30 ]; then
    LOG "ERROR: docker did not become ready"
    exit 1
  fi
done

# ---- 4) Ensure ubuntu user can use docker without sudo (optional) ----
if id -u ubuntu >/dev/null 2>&1; then
  LOG "Adding ubuntu to docker group"
  usermod -aG docker ubuntu || true
fi

# ---- 5) Ensure .env contains HOST_PRIVATE_IP for advertised listeners ----
HOST_PRIVATE_IP=""
if curl -s --max-time 2 http://169.254.169.254/latest/meta-data/local-ipv4 >/dev/null 2>&1; then
  HOST_PRIVATE_IP="$(curl -s http://169.254.169.254/latest/meta-data/local-ipv4)"
fi
if [ -z "$HOST_PRIVATE_IP" ]; then
  LOG "No metadata IP found; leaving HOST_PRIVATE_IP blank in .env"
fi

LOG "Writing ${ENV_FILE} with HOST_PRIVATE_IP=${HOST_PRIVATE_IP}"
printf '%s\n' "HOST_PRIVATE_IP=${HOST_PRIVATE_IP}" > "${ENV_FILE}"
chown ubuntu:ubuntu "${ENV_FILE}" || true
chmod 644 "${ENV_FILE}"

# ---- 6) Find docker-compose.yml in candidate locations ----
COMPOSE_FILE=""
for candidate in "${COMPOSE_CANDIDATES[@]}"; do
  if [ -f "$candidate" ]; then
    COMPOSE_FILE="$candidate"
    break
  fi
done

if [ -z "$COMPOSE_FILE" ]; then
  LOG "ERROR: no docker-compose.yml found in candidates:"
  for c in "${COMPOSE_CANDIDATES[@]}"; do LOG " - $c"; done
  exit 1
fi
echo "[kafka_install] Using compose file: $COMPOSE_FILE"

# Decide docker compose command
if command -v docker compose >/dev/null 2>&1; then
  DC_CMD="docker compose"
elif command -v docker-compose >/dev/null 2>&1; then
  DC_CMD="docker-compose"
else
  echo "[kafka_install] ERROR: neither 'docker compose' nor 'docker-compose' found"
  exit 1
fi

echo "[kafka_install] Pulling images ($DC_CMD pull)..."
$DC_CMD -f "$COMPOSE_FILE" pull || {
  echo "[kafka_install] WARNING: $DC_CMD pull failed (continuing anyway)"
}

echo "[kafka_install] Starting docker compose stack..."
$DC_CMD -f "$COMPOSE_FILE" up -d

echo "[kafka_install] Kafka stack containers:"
docker ps --format "table {{.Names}}\t{{.Image}}\t{{.Status}}"
