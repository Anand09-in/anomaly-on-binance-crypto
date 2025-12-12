data "template_file" "mlflow_user_data" {
  template = file("${path.module}/mlflow_user_data.sh.tpl")

  vars = {
    S3_BUCKET     = aws_s3_bucket.mlflow_artifacts.bucket
    DB_SECRET_ARN = aws_secretsmanager_secret.mlflow_db_secret.arn
    REGION        = var.region
  }
}



resource "aws_instance" "mlflow_ec2" {
  ami                    = data.aws_ami.ubuntu.id
  instance_type          = var.mlflow_instance_type
  subnet_id              = var.public_subnet_ids[0]
  iam_instance_profile   = aws_iam_instance_profile.mlflow_instance_profile.name
  security_groups        = [aws_security_group.mlflow_ec2_sg.id]
  key_name               = var.key_name  
  user_data              = data.template_file.mlflow_user_data.rendered

  tags = {
    Name = "${var.project_name}-mlflow-ec2"
  }

  depends_on = [aws_iam_role_policy_attachment.attach_s3]
}

data "aws_ami" "ubuntu" {
  most_recent = true
  owners      = ["099720109477"] # Canonical
  filter {
    name   = "name"
    values = ["ubuntu/images/hvm-ssd/ubuntu-jammy-22.04-amd64-server-*"]
  }
}
