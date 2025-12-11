variable "region" {
  description = "AWS region"
  default     = "ap-south-1"
}

variable "allowed_ip" {
  description = "Your public IP for MLflow ALB access"
  default     = "122.172.83.89/32"
}


variable "eks_cluster_name" {
  default = "crypto-ml-eks"
}

variable "node_group_instance_types" {
  default = ["c7i-flex.large"]
}

variable "node_group_size" {
  default = 2
}
variable "project_name" {
  type    = string
  default = "crypto-anom-ml"
}


variable "key_name" {
  type        = string
  description = "EC2 key pair name for SSH access"
  default= "anom-ec2-ssh-key"
}