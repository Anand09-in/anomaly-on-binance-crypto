terraform {
  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 5.0"
    }
  }
  required_version = ">= 1.2"
}

provider "aws" {
  region  = "ap-south-1"
  profile = "anomprofile"
}

data "aws_availability_zones" "available" {}

# Simple VPC + single public subnet
resource "aws_vpc" "main" {
  cidr_block           = "10.10.0.0/16"
  enable_dns_hostnames = true
  enable_dns_support   = true
  tags                 = { Name = "${var.project_name}-vpc" }
}

resource "aws_internet_gateway" "igw" {
  vpc_id = aws_vpc.main.id
  tags   = { Name = "${var.project_name}-igw" }
}

resource "aws_subnet" "public" {
  vpc_id                  = aws_vpc.main.id
  cidr_block              = "10.10.1.0/24"
  map_public_ip_on_launch = true
  availability_zone       = data.aws_availability_zones.available.names[0]
  tags                    = { Name = "${var.project_name}-public-subnet" }
}

resource "aws_route_table" "public" {
  vpc_id = aws_vpc.main.id
  route {
    cidr_block = "0.0.0.0/0"
    gateway_id = aws_internet_gateway.igw.id
  }
  tags = { Name = "${var.project_name}-public-rt" }
}

resource "aws_route_table_association" "public_assoc" {
  subnet_id      = aws_subnet.public.id
  route_table_id = aws_route_table.public.id
}

# Security group: HTTP (optional), SSH, Kafka ports (9092-9094)
resource "aws_security_group" "sg" {
  name        = "${var.project_name}-sg"
  description = "SG for kafka node"
  vpc_id      = aws_vpc.main.id

  ingress {
    description = "SSH"
    from_port   = 22
    to_port     = 22
    protocol    = "tcp"
    cidr_blocks = ["122.172.85.177/32"] # Change to your IP
  }

  # kafka ports (private/public depending on need). Restrict as you wish.
  ingress {
    description = "Kafka brokers"
    from_port   = 9092
    to_port     = 9094
    protocol    = "tcp"
    cidr_blocks = [aws_vpc.main.cidr_block]
  }

  # Zookeeper
  ingress {
    description = "Zookeeper"
    from_port   = 2181
    to_port     = 2181
    protocol    = "tcp"
    cidr_blocks = [aws_vpc.main.cidr_block]
  }

  egress {
    from_port   = 0
    to_port     = 0
    protocol    = "-1"
    cidr_blocks = ["0.0.0.0/0"]
  }

  tags = { Name = "${var.project_name}-sg" }
}


# Find Ubuntu AMI
data "aws_ami" "ubuntu" {
  most_recent = true
  owners      = ["099720109477"]
  filter {
    name   = "name"
    values = ["ubuntu/images/hvm-ssd/ubuntu-jammy-22.04-amd64-server-*"]
  }
}

# EC2 instance
resource "aws_instance" "kafka_node" {
  ami                    = data.aws_ami.ubuntu.id
  instance_type          = var.instance_type
  subnet_id              = aws_subnet.public.id
  vpc_security_group_ids = [aws_security_group.sg.id]
  key_name               = var.key_name



  associate_public_ip_address = true

  # USER DATA: installs docker, git, awscli; clones repo; runs docker compose
  user_data = <<-EOF
                #!/bin/bash
                set -euo pipefail
                export DEBIAN_FRONTEND=noninteractive

                apt-get update -y
                apt-get install -y git unzip curl

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

                # run install script
                INSTALL_SCRIPT="$${REPO_DIR}/Kafka/Setup/kafka_install.sh"
                if [ ! -f "$${INSTALL_SCRIPT}" ]; then
                echo "ERROR: $${INSTALL_SCRIPT} not found"
                exit 1
                fi
                chmod +x "$${INSTALL_SCRIPT}"
                echo "Executing kafka_install.sh..."
                "$${INSTALL_SCRIPT}" || { echo "kafka_install.sh failed"; exit 1; }


                # run producer env script
                PRODUCER_SCRIPT="$${REPO_DIR}/Kafka/Producer/producer_start.sh"
                if [ ! -f "$${PRODUCER_SCRIPT}" ]; then
                echo "ERROR: $${PRODUCER_SCRIPT} not found"
                exit 1
                fi
                chmod +x "$${PRODUCER_SCRIPT}"
                echo "Starting Producer ..."
                "$${PRODUCER_SCRIPT}" || { echo "producer_start.sh failed"; exit 1; }

                EOF



  tags = { Name = "${var.project_name}-kafka-node" }
}

output "public_ip" {
  value = aws_instance.kafka_node.public_ip
}

output "private_ip" {
  value = aws_instance.kafka_node.private_ip
}

output "bootstrap_servers" {
  value = "${aws_instance.kafka_node.private_ip}:9092,${aws_instance.kafka_node.private_ip}:9093,${aws_instance.kafka_node.private_ip}:9094"
}
