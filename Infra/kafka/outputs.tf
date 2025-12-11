output "kafka_public_ip" {
  value = aws_instance.kafka_node.public_ip
}

output "kafka_private_ip" {
  value = aws_instance.kafka_node.private_ip
}
