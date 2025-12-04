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


