# ALB Security Group: allows incoming HTTP from allowed IP only
resource "aws_security_group" "mlflow_alb_sg" {
  name   = "${var.project_name}-mlflow-alb-sg"
  vpc_id = var.vpc_id

  ingress {
    from_port   = 80
    to_port     = 80
    protocol    = "tcp"
    cidr_blocks = [var.allowed_ip]
    description = "Allow HTTP from your IP"
  }

  egress {
    from_port   = 0
    to_port     = 0
    protocol    = "-1"
    cidr_blocks = ["0.0.0.0/0"]
  }

  tags = { Name = "${var.project_name}-mlflow-alb-sg" }
}

# EC2 security group: allow only SSH from your IP and HTTP from ALB SG
resource "aws_security_group" "mlflow_ec2_sg" {
  name   = "${var.project_name}-mlflow-ec2-sg"
  vpc_id = var.vpc_id

  ingress {
    from_port   = 22
    to_port     = 22
    protocol    = "tcp"
    cidr_blocks = [var.allowed_ip]
    description = "SSH from your IP"
  }

  ingress {
    from_port       = 80
    to_port         = 80
    protocol        = "tcp"
    security_groups = [aws_security_group.mlflow_alb_sg.id]
    description     = "Allow HTTP from ALB"
  }

  egress {
    from_port   = 0
    to_port     = 0
    protocol    = "-1"
    cidr_blocks = ["0.0.0.0/0"]
  }

  tags = { Name = "${var.project_name}-mlflow-ec2-sg" }
}

# RDS SG: allow connection from EC2 only
resource "aws_security_group" "mlflow_db_sg" {
  name   = "${var.project_name}-mlflow-db-sg"
  vpc_id = var.vpc_id

  ingress {
    from_port       = 5432
    to_port         = 5432
    protocol        = "tcp"
    security_groups = [aws_security_group.mlflow_ec2_sg.id]
    description     = "Allow Postgres from MLflow EC2"
  }

  egress {
    from_port   = 0
    to_port     = 0
    protocol    = "-1"
    cidr_blocks = ["0.0.0.0/0"]
  }

  tags = { Name = "${var.project_name}-mlflow-db-sg" }
}
