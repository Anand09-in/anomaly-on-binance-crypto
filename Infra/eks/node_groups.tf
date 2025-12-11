resource "aws_eks_node_group" "default" {
  cluster_name    = aws_eks_cluster.main.name
  node_group_name = "${var.eks_cluster_name}-ng"
  node_role_arn   = aws_iam_role.eks_node_role.arn

  subnet_ids = [
    var.subnet_ids[0],
    var.subnet_ids[1]   # use the first (your public subnet)
  ]

  scaling_config {
    desired_size = var.node_group_size
    max_size     = var.node_group_size + 1
    min_size     = 1
  }

  instance_types = var.node_group_instances

  tags = {
    Name = "${var.eks_cluster_name}-node-group"
  }

  depends_on = [
    aws_eks_cluster.main
  ]
}

