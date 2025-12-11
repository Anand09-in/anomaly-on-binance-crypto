variable "aws_region" {
  type    = string
  default = "ap-south-1"
}

variable "instance_type" {
  type    = string
  default = "c7i-flex.large"
}

variable "key_name" {
  type        = string
  description = "EC2 key pair name for SSH access"
  default= "anom-ec2-ssh-key"
}

variable "project_name" {
  type    = string
  default = "crypto-anom-ml"
}

# Repo to clone (HTTPS or SSH form as needed)
variable "git_repo_url" {
  type        = string
  default     = "https://github.com/Anand09-in/anomaly-on-binance-crypto.git"
  description = "Repository containing docker-compose (public HTTPS URL or SSH URL for private)"
}

variable "git_repo_branch" {
  type    = string
  default = "main"
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


variable "vpc_id" {
  type = string
}
variable "vpc_cidr" {
  type = string
}
variable "public_subnet_id" {
  type = string
}

variable "allowed_ip" {
  type = string
  default = "122.172.85.177/32"
}


