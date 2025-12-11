variable "eks_cluster_name" {
  description = "Name of the EKS cluster"
  type        = string
  default     = "crypto-ml-eks"
}

# variable "private_subnet_ids" {
#   type = list(string)
# }

variable "project_name" {
  type        = string
  description = "Prefix for tagging and naming EKS resources"
}

variable "region" {
  type        = string
  description = "AWS region"
}
variable "vpc_id" {
  type        = string
  description = "VPC ID for EKS"
}

variable "subnet_ids" {
  type        = list(string)
  description = "Subnets for EKS nodes and control plane"
}


variable "node_group_size" {
  default = 2
}
variable "node_group_instances" {
  default = ["c7i-flex.large"]
}