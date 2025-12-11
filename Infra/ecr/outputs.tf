output "producer_repo_url" {
  value = aws_ecr_repository.producer.repository_url
}

output "flink_inference_repo_url" {
  value = aws_ecr_repository.flink_inference.repository_url
}

output "spark_training_repo_url" {
  value = aws_ecr_repository.spark_training.repository_url
}
