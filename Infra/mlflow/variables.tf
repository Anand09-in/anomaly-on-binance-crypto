variable "project_name" {
  type    = string
  default = "crypto-anom-ml"
}


variable "region" {
  type    = string
  default = "ap-south-1"
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
  default = "t3.small"
}
