output "mlflow_alb_dns" {
  value = aws_lb.mlflow_alb.dns_name
}

output "mlflow_ec2_public_ip" {
  value = aws_instance.mlflow_ec2.public_ip
}

output "mlflow_s3_bucket" {
  value = aws_s3_bucket.mlflow_artifacts.bucket
}

output "mlflow_db_endpoint" {
  value = aws_db_instance.postgres.address
}
