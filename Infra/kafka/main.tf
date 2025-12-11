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

                  apt-get update -y
                  apt-get install -y git unzip curl docker.io docker-compose awscli

                  systemctl enable docker
                  systemctl start docker

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
                    echo "Repo exists, updating branch $${BRANCH}"
                    cd "$${REPO_DIR}"
                    sudo -u ubuntu git fetch --all --prune
                    sudo -u ubuntu git checkout "$${BRANCH}" || sudo -u ubuntu git checkout -b "$${BRANCH}" origin/"$${BRANCH}"
                    sudo -u ubuntu git reset --hard origin/"$${BRANCH}"
                  else
                    echo "Cloning repository ${var.git_repo_url} (branch ${var.git_repo_branch}) into $${REPO_DIR}"
                    sudo -u ubuntu git clone -b "${var.git_repo_branch}" "${var.git_repo_url}" "$${REPO_DIR}" || { echo "git clone failed"; exit 1; }
                  fi

                  # --- KAFKA INFRA SETUP (stays in Terraform user_data) ---
                  INSTALL_SCRIPT="$${REPO_DIR}/Infra/kafka/kafka_install.sh"
                  if [ ! -f "$${INSTALL_SCRIPT}" ]; then
                    echo "ERROR: $${INSTALL_SCRIPT} not found"
                    exit 1
                  fi
                  chmod +x "$${INSTALL_SCRIPT}"
                  echo "Executing kafka_install.sh..."
                  "$${INSTALL_SCRIPT}" || { echo "kafka_install.sh failed"; exit 1; }

                  echo "Kafka infra is up. Producer will be deployed via CI/CD."
                EOF



  tags = {
    Name = "${var.project_name}-kafka-node"
  }
}
