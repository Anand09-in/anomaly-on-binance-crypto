resource "random_password" "rds_password" {
  length          = 16
  special         = true
  override_special = "!@#"
}
resource "aws_db_subnet_group" "mlflow_db_subnet" {
  name       = "${var.project_name}-db-subnet"
  subnet_ids = var.public_subnet_ids  # using public subnets here since single-AZ; adjust if private subnets used
  tags = {
    Name = "${var.project_name}-db-subnet"
  }
}

resource "aws_db_instance" "postgres" {
  identifier = "${var.project_name}-mlflow-db"
  engine     = "postgres"
  instance_class = "db.t3.micro"
  allocated_storage = 20
  username          = "mlflowuser"
  password          = random_password.rds_password.result
  skip_final_snapshot = true
  db_subnet_group_name = aws_db_subnet_group.mlflow_db_subnet.name
  publicly_accessible  = false
  multi_az = false
  vpc_security_group_ids = [aws_security_group.mlflow_db_sg.id]

  tags = {
    Name = "${var.project_name}-mlflow-db"
  }
}
