output "eks_cluster_name" {
  value = var.eks_cluster_name
}

output "mlflow_url" {
  value = module.mlflow.mlflow_alb_dns
}

output "s3_buckets" {
  value = module.s3.bucket_names
}
