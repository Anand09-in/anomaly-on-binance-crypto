resource "aws_lb" "mlflow_alb" {
  name               = "${var.project_name}-mlflow-alb"
  internal           = false
  load_balancer_type = "application"
  security_groups    = [aws_security_group.mlflow_alb_sg.id]
  subnets            = var.public_subnet_ids

  tags = {
    Name = "${var.project_name}-mlflow-alb"
  }
}

resource "aws_lb_target_group" "mlflow_tg" {
  name     = "${var.project_name}-mlflow-tg"
  port     = 80
  protocol = "HTTP"
  vpc_id   = var.vpc_id
  health_check {
    path = "/"
    port = "80"
    protocol = "HTTP"
  }
}

resource "aws_lb_listener" "mlflow_listener" {
  load_balancer_arn = aws_lb.mlflow_alb.arn
  port              = "80"
  protocol          = "HTTP"

  default_action {
    type = "forward"
    target_group_arn = aws_lb_target_group.mlflow_tg.arn
  }
}

resource "aws_lb_target_group_attachment" "mlflow_attach" {
  target_group_arn = aws_lb_target_group.mlflow_tg.arn
  target_id        = aws_instance.mlflow_ec2.id
  port             = 80
}
