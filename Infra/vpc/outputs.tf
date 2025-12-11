output "vpc_id" {
  value = aws_vpc.main.id
}
output "cidr_block" {
  value = aws_vpc.main.cidr_block
}

output "subnet_ids" {
  value = [
    aws_subnet.public_a.id,
    aws_subnet.public_b.id,
  ]
}

output "public_subnet_a_id" {
  value = aws_subnet.public_a.id
}

output "public_subnet_b_id" {
  value = aws_subnet.public_b.id
}
