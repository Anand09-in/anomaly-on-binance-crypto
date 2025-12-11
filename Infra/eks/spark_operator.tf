resource "helm_release" "spark_operator" {
  name       = "spark-operator"
  repository = "https://googlecloudplatform.github.io/spark-on-k8s-operator"
  chart      = "spark-operator"
  namespace  = "spark-operator"
  create_namespace = true

  set {
    name  = "sparkJobNamespace"
    value = "spark-jobs"
  }

  set {
    name  = "enableWebhook"
    value = "true"
  }

  depends_on = [
    aws_eks_cluster.main,
    aws_eks_node_group.default
  ]
}
