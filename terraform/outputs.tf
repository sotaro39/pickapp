# PickApp - 出力値

output "vpc_id" {
  description = "VPC ID"
  value       = aws_vpc.main.id
}

output "public_subnet_ids" {
  description = "パブリックサブネットID"
  value       = aws_subnet.public[*].id
}

output "private_subnet_ids" {
  description = "プライベートサブネットID"
  value       = aws_subnet.private[*].id
}

output "ec2_public_ip" {
  description = "EC2のパブリックIP (Elastic IP)"
  value       = aws_eip.app.public_ip
}

output "ec2_instance_id" {
  description = "EC2インスタンスID"
  value       = aws_instance.app.id
}

output "rds_endpoint" {
  description = "RDSエンドポイント"
  value       = aws_db_instance.main.endpoint
}

output "rds_address" {
  description = "RDSホスト名"
  value       = aws_db_instance.main.address
}

output "app_url" {
  description = "アプリケーションURL"
  value       = "http://${aws_eip.app.public_ip}"
}

output "ssh_command" {
  description = "SSH接続コマンド"
  value       = "ssh -i ~/.ssh/${var.ec2_key_name}.pem ec2-user@${aws_eip.app.public_ip}"
}

output "database_url" {
  description = "データベース接続URL (機密情報)"
  value       = "postgresql+asyncpg://${var.db_username}:****@${aws_db_instance.main.address}:5432/${var.db_name}"
  sensitive   = true
}
