resource "aws_ecr_repository" "spark_training" {
  name = "${var.project_name}-spark-training"

  image_scanning_configuration {
    scan_on_push = true
  }
}
