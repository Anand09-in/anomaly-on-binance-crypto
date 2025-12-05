#!/usr/bin/env bash
set -euo pipefail

LOG() { echo "[$(date -u +'%Y-%m-%dT%H:%M:%SZ')] [producer_install] $*"; }

LOG "Starting producer_install.sh"

# -----------------------------------------------------
# 1) Path setup
# -----------------------------------------------------
PRODUCER_DIR="$(dirname "$(realpath "$0")")"
ENV_JSON="${PRODUCER_DIR}/config.json"
ENV_FILE="${PRODUCER_DIR}/.env"

LOG "Producer directory: ${PRODUCER_DIR}"

if [ ! -f "$ENV_JSON" ]; then
  LOG "ERROR: env.json not found at $ENV_JSON"
  exit 1
fi

# -----------------------------------------------------
# 2) Fetch EC2 private IP
# -----------------------------------------------------
HOST_PRIVATE_IP="$(curl -s http://169.254.169.254/latest/meta-data/local-ipv4 || true)"

if [ -z "$HOST_PRIVATE_IP" ]; then
  LOG "WARNING: Could not detect private IP."
fi

# -----------------------------------------------------
# 3) Convert env.json -> .env
# -----------------------------------------------------
LOG "Generating .env from env.json"

{
  echo "###########################################"
  echo "# AUTO-GENERATED PRODUCER .env (DO NOT COMMIT)"
  echo "###########################################"
  echo ""
  echo "# Dynamic EC2 private IP"
  echo "HOST_PRIVATE_IP=${HOST_PRIVATE_IP}"
  echo ""

  # Convert JSON fields into KEY=VALUE lines
  jq -r 'to_entries | .[] | "\(.key)=\(.value)"' "$ENV_JSON"

} > "$ENV_FILE"

chmod 644 "$ENV_FILE"

LOG ".env created:"
LOG "$(cat "$ENV_FILE")"

# -----------------------------------------------------
# 4) Locate docker-compose file
# -----------------------------------------------------
COMPOSE_CANDIDATES=(
  "${PRODUCER_DIR}/docker-compose.yaml"
  "${PRODUCER_DIR}/Producer/docker-compose.yaml"
  "${PRODUCER_DIR}/Kafka/Producer/docker-compose.yaml"
)

COMPOSE_FILE=""
for candidate in "${COMPOSE_CANDIDATES[@]}"; do
  if [ -f "$candidate" ]; then
    COMPOSE_FILE="$candidate"
    break
  fi
done

if [ -z "$COMPOSE_FILE" ]; then
  LOG "ERROR: No producer docker-compose.yaml found."
  exit 1
fi

LOG "Using compose file: ${COMPOSE_FILE}"

# -----------------------------------------------------
# 5) Pull and start producer container
# -----------------------------------------------------
LOG "Pulling producer image..."
docker compose --env-file "$ENV_FILE" -f "$COMPOSE_FILE" pull || LOG "pull failed (continuing)"

LOG "Starting producer container..."
docker compose --env-file "$ENV_FILE" -f "$COMPOSE_FILE" up -d

docker compose --env-file "$ENV_FILE" -f "$COMPOSE_FILE" ps

LOG "Producer installation complete."
exit 0
