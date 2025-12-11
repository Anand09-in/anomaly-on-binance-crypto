resource "aws_iam_role" "mlflow_ec2_role" {
  name = "${var.project_name}-mlflow-ec2-role"
  assume_role_policy = jsonencode({
    Version = "2012-10-17",
    Statement = [{
      Action = "sts:AssumeRole",
      Effect = "Allow",
      Principal = {
        Service = "ec2.amazonaws.com"
      }
    }]
  })
}

resource "aws_iam_policy" "mlflow_s3_policy" {
  name = "${var.project_name}-mlflow-s3-policy"
  policy = jsonencode({
    Version = "2012-10-17",
    Statement = [
      {
        Effect = "Allow",
        Action = [
          "s3:GetObject",
          "s3:PutObject",
          "s3:ListBucket",
          "s3:DeleteObject"
        ],
        Resource = [
          aws_s3_bucket.mlflow_artifacts.arn,
          "${aws_s3_bucket.mlflow_artifacts.arn}/*"
        ]
      }
    ]
  })
}

resource "aws_iam_policy" "secretsmanager_policy" {
  name = "${var.project_name}-secretsmanager-policy"
  policy = jsonencode({
    Version = "2012-10-17",
    Statement = [
      {
        Effect = "Allow",
        Action = [
          "secretsmanager:GetSecretValue"
        ],
        Resource = "*"
      }
    ]
  })
}

resource "aws_iam_role_policy_attachment" "attach_s3" {
  role       = aws_iam_role.mlflow_ec2_role.name
  policy_arn = aws_iam_policy.mlflow_s3_policy.arn
}

resource "aws_iam_role_policy_attachment" "attach_sm" {
  role       = aws_iam_role.mlflow_ec2_role.name
  policy_arn = aws_iam_policy.secretsmanager_policy.arn
}

resource "aws_iam_instance_profile" "mlflow_instance_profile" {
  name = "${var.project_name}-mlflow-instance-profile"
  role = aws_iam_role.mlflow_ec2_role.name
}
