resource "aws_ecr_repository" "flink_inference" {
  name = "${var.project_name}-flink-inference"

  image_scanning_configuration {
    scan_on_push = true
  }
}
