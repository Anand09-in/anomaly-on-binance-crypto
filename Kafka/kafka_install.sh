#!/usr/bin/env bash
set -euo pipefail
export DEBIAN_FRONTEND=noninteractive

LOG() { echo "[$(date -u +'%Y-%m-%dT%H:%M:%SZ')] $*"; }

# ---- Configurable vars ----
REPO_DIR="$(dirname "$(realpath "$0")")"   # script location => repo root if placed at repo root
COMPOSE_CANDIDATES=(
  "${REPO_DIR}/docker-compose.yaml"
  "${REPO_DIR}/Kafka/docker-compose.yaml"
  "${REPO_DIR}/compose/docker-compose.yaml"
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
LOG "Using compose file: ${COMPOSE_FILE}"

# ---- 7) Pull latest images (optional) ----
LOG "Pulling images (docker compose pull)..."
docker compose --env-file "${ENV_FILE}" -f "${COMPOSE_FILE}" pull || LOG "docker compose pull returned non-zero (continuing)"

# ---- 8) Start the stack (idempotent) ----
LOG "Starting docker compose stack"
docker compose --env-file "${ENV_FILE}" -f "${COMPOSE_FILE}" up -d

# ---- 9) Verify containers are running (simple check) ----
sleep 3
LOG "Checking container status for compose stack"
if docker compose --env-file "${ENV_FILE}" -f "${COMPOSE_FILE}" ps; then
  LOG "Compose stack started (see 'docker compose ps' output above)"
else
  LOG "WARNING: docker compose ps returned non-zero"
fi

LOG "kafka_install.sh completed successfully"
exit 0
