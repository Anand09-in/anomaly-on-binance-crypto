data "aws_availability_zones" "available" {}

resource "aws_security_group" "sg" {
  name        = "${var.project_name}-sg"
  description = "SG for kafka node"
  vpc_id      = var.vpc_id

  ingress {
    description = "SSH"
    from_port   = 22
    to_port     = 22
    protocol    = "tcp"
    cidr_blocks = [var.allowed_ip]
  }

  ingress {
    description = "Kafka brokers"
    from_port   = 9092
    to_port     = 9094
    protocol    = "tcp"
    cidr_blocks = [var.vpc_cidr]
  }

  ingress {
    description = "Zookeeper"
    from_port   = 2181
    to_port     = 2181
    protocol    = "tcp"
    cidr_blocks = [var.vpc_cidr]
  }

  egress {
    from_port   = 0
    to_port     = 0
    protocol    = "-1"
    cidr_blocks = ["0.0.0.0/0"]
  }
}

# data "aws_ami" "ubuntu" {
#   most_recent = true
#   owners      = ["099720109477"]
#   filter {
#     name   = "name"
#     values = ["ubuntu/images/hvm-ssd/ubuntu-jammy-22.04-amd64-server-*"]
#   }
# }

resource "aws_instance" "kafka_node" {
  ami                    = data.aws_ami.ubuntu.id
  instance_type          = var.instance_type
  subnet_id              = var.public_subnet_id
  vpc_security_group_ids = [aws_security_group.sg.id]
  key_name               = var.key_name  
  associate_public_ip_address = true


  user_data = <<-EOF
                  #!/bin/bash
                  set -euo pipefail
                  export DEBIAN_FRONTEND=noninteractive

                  echo "[user_data] Starting bootstrapping..."

                  # Basic tools
                  apt-get update -y
                  apt-get install -y apt-transport-https ca-certificates curl gnupg lsb-release unzip git jq

                  # Install Docker Engine + Compose v2 plugin (official)
                  echo "[user_data] Installing Docker Engine and Compose v2..."
                  if ! command -v docker >/dev/null 2>&1 || ! docker compose version >/dev/null 2>&1; then
                    # Add Docker's official GPG key and repo
                    mkdir -p /etc/apt/keyrings
                    curl -fsSL https://download.docker.com/linux/ubuntu/gpg | gpg --dearmor -o /etc/apt/keyrings/docker.gpg
                    echo \
                      "deb [arch=$(dpkg --print-architecture) signed-by=/etc/apt/keyrings/docker.gpg] \
                      https://download.docker.com/linux/ubuntu \
                      $(lsb_release -cs) stable" \
                      | tee /etc/apt/sources.list.d/docker.list > /dev/null

                    apt-get update -y
                    apt-get install -y docker-ce docker-ce-cli containerd.io docker-buildx-plugin docker-compose-plugin
                  else
                    echo "[user_data] Docker + docker compose already installed"
                  fi

                  # Ensure docker service is enabled and running
                  systemctl enable docker
                  systemctl start docker

                  # Add ubuntu user to docker group (so sudo not required for docker)
                  if id -u ubuntu >/dev/null 2>&1; then
                    usermod -aG docker ubuntu || true
                  fi

                  # Install AWS CLI v2 if not present (useful for ECR login etc)
                  if ! command -v aws >/dev/null 2>&1; then
                    echo "[user_data] Installing AWS CLI v2..."
                    curl "https://awscli.amazonaws.com/awscli-exe-linux-x86_64.zip" -o "/tmp/awscliv2.zip"
                    unzip -o /tmp/awscliv2.zip -d /tmp
                    /tmp/aws/install -i /usr/local/aws-cli -b /usr/local/bin || true
                    rm -rf /tmp/aws /tmp/awscliv2.zip
                  fi

                  # Prepare ubuntu home
                  mkdir -p /home/ubuntu
                  chown ubuntu:ubuntu /home/ubuntu

                  # Repo variables (Terraform will substitute var.git_repo_url and var.git_repo_branch)
                  REPO_URL="${var.git_repo_url}"
                  BRANCH="${var.git_repo_branch}"
                  REPO_DIR="/home/ubuntu/repo"

                  mkdir -p "$${REPO_DIR}"
                  chown ubuntu:ubuntu "$${REPO_DIR}"

                  # clone or update repository (idempotent)
                  if [ -d "$${REPO_DIR}/.git" ]; then
                    echo "[user_data] Repo exists, updating branch $${BRANCH}"
                    cd "$${REPO_DIR}"
                    sudo -u ubuntu git fetch --all --prune
                    sudo -u ubuntu git checkout "$${BRANCH}" || sudo -u ubuntu git checkout -b "$${BRANCH}" origin/"$${BRANCH}"
                    sudo -u ubuntu git reset --hard origin/"$${BRANCH}"
                  else
                    echo "[user_data] Cloning repository ${var.git_repo_url} (branch ${var.git_repo_branch}) into $${REPO_DIR}"
                    sudo -u ubuntu git clone -b "${var.git_repo_branch}" "${var.git_repo_url}" "$${REPO_DIR}" || { echo "[user_data] git clone failed"; exit 1; }
                  fi

                  # Ensure docker plugin is available through PATH for ubuntu user (login shells)
                  # (This helps when CI sshs and runs docker compose as ubuntu)
                  if ! sudo -u ubuntu docker compose version >/dev/null 2>&1; then
                    echo "[user_data] Note: 'docker compose' not yet available to ubuntu user in this shell; it will be available on next login."
                  fi

                  # --- KAFKA INFRA SETUP (stays in Terraform user_data) ---
                  INSTALL_SCRIPT="$${REPO_DIR}/Infra/kafka/kafka_install.sh"
                  if [ ! -f "$${INSTALL_SCRIPT}" ]; then
                    echo "[user_data] ERROR: $${INSTALL_SCRIPT} not found"
                    exit 1
                  fi
                  chmod +x "$${INSTALL_SCRIPT}"
                  echo "[user_data] Executing kafka_install.sh..."
                  # Run kafka_install as ubuntu so files created under /home/ubuntu are owned by ubuntu
                  sudo -u ubuntu bash -c "$${INSTALL_SCRIPT}" || { echo "[user_data] kafka_install.sh failed"; exit 1; }

                  echo "[user_data] Kafka infra is up. Producer will be deployed via CI/CD."
                EOF




  tags = {
    Name = "${var.project_name}-kafka-node"
  }
}
