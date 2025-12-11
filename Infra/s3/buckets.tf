variable "project_name" {
  type = string
}

resource "aws_s3_bucket" "models" {
  bucket = "${var.project_name}-models"
}

resource "aws_s3_bucket" "features" {
  bucket = "${var.project_name}-features"
}

resource "aws_s3_bucket" "dvc" {
  bucket = "${var.project_name}-dvc"
}

resource "aws_s3_bucket" "checkpoints" {
  bucket = "${var.project_name}-checkpoints"
}
