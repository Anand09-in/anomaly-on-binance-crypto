output "bucket_names" {
  value = {
    models      = aws_s3_bucket.models.bucket
    features    = aws_s3_bucket.features.bucket
    dvc         = aws_s3_bucket.dvc.bucket
    checkpoints = aws_s3_bucket.checkpoints.bucket
  }
}
