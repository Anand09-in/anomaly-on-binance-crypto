resource "aws_ecr_repository" "producer" {
  name = "${var.project_name}-binance-producer"

  image_scanning_configuration {
    scan_on_push = true
  }
}
