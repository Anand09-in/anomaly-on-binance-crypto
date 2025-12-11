resource "helm_release" "flink_k8s_operator" {
  name             = "flink-kubernetes-operator"
  repository       = "https://downloads.apache.org/flink/flink-kubernetes-operator-1.7.0"
  chart            = "flink-kubernetes-operator"
  namespace        = "flink-operator"
  create_namespace = true

  depends_on = [
    aws_eks_cluster.main,
    aws_eks_node_group.default
  ]
}
