# PickApp - RDS (PostgreSQL)

resource "aws_db_instance" "main" {
  identifier = "${var.project_name}-db"

  # エンジン設定
  engine               = "postgres"
  engine_version       = "15.17"
  instance_class       = var.db_instance_class
  allocated_storage    = 20
  max_allocated_storage = 100  # オートスケーリング上限
  storage_type         = "gp3"

  # データベース設定
  db_name  = var.db_name
  username = var.db_username
  password = var.db_password
  port     = 5432

  # ネットワーク設定
  db_subnet_group_name   = aws_db_subnet_group.main.name
  vpc_security_group_ids = [aws_security_group.rds.id]
  publicly_accessible    = false  # EC2からのみアクセス

  # バックアップ設定
  backup_retention_period = 7
  backup_window          = "03:00-04:00"  # UTC (JST 12:00-13:00)
  maintenance_window     = "Mon:04:00-Mon:05:00"

  # パラメータ
  parameter_group_name = aws_db_parameter_group.main.name

  # その他設定
  skip_final_snapshot       = true  # 開発用（本番ではfalse推奨）
  deletion_protection       = false # 開発用（本番ではtrue推奨）
  auto_minor_version_upgrade = true
  copy_tags_to_snapshot     = true

  tags = {
    Name = "${var.project_name}-db"
  }
}

# RDS Parameter Group
resource "aws_db_parameter_group" "main" {
  name   = "${var.project_name}-pg15-params"
  family = "postgres15"

  parameter {
    name  = "timezone"
    value = "Asia/Tokyo"
  }

  parameter {
    name  = "log_statement"
    value = "all"
  }

  tags = {
    Name = "${var.project_name}-pg15-params"
  }
}
