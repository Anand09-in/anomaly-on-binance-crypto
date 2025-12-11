resource "aws_secretsmanager_secret" "mlflow_db_secret" {
  name = "${var.project_name}-mlflow-db-secret"
}

resource "aws_secretsmanager_secret_version" "mlflow_db_secret_version" {
  secret_id     = aws_secretsmanager_secret.mlflow_db_secret.id
  secret_string = jsonencode({
    username = "mlflowuser",
    password = random_password.rds_password.result,
    host     = aws_db_instance.postgres.address,
    port     = aws_db_instance.postgres.port,
    dbname   = aws_db_instance.postgres.identifier
  })
}
