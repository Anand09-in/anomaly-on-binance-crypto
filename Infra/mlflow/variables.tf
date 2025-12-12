variable "project_name" {
  type    = string
  default = "crypto-anom-ml"
}


variable "region" {
  type    = string
  default = "ap-south-1"
}
variable "key_name" {
  type        = string
  description = "EC2 key pair name for SSH access"
  default= "anom-ec2-ssh-key"
}

variable "allowed_ip" {
  type    = string
  # already provided
}

variable "vpc_id" {
  type = string
  description = "Existing VPC id"
}

variable "public_subnet_ids" {
  type = list(string)
  description = "Public subnet ids in the VPC"
}

variable "mlflow_instance_type" {
  type    = string
  default = "c7i-flex.large"
}


variable "db_username" {
  type        = string
  description = "DB username for mlflow (rendered into user-data)"
}

variable "db_password" {
  type        = string
  description = "DB password for mlflow"
  sensitive   = true
}

variable "db_name" {
  type        = string
  description = "DB name for mlflow"
  default     = "mlflow"
}

variable "s3_bucket" {
  type        = string
  description = "S3 bucket for mlflow artifacts"
}
