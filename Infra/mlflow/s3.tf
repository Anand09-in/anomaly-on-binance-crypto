resource "aws_s3_bucket" "mlflow_artifacts" {
  bucket = "${var.project_name}-artifacts"
  acl    = "private"

  server_side_encryption_configuration {
    rule {
      apply_server_side_encryption_by_default {
        sse_algorithm = "AES256"
      }
    }
  }

  versioning {
    enabled = true
  }

  tags = {
    Project = var.project_name
    Environment = "prod"
  }
}
