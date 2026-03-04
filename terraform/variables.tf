# PickApp - 変数定義

variable "aws_region" {
  description = "AWSリージョン"
  type        = string
  default     = "us-east-2"
}

variable "environment" {
  description = "環境名 (dev/staging/prod)"
  type        = string
  default     = "dev"
}

variable "project_name" {
  description = "プロジェクト名"
  type        = string
  default     = "pickapp"
}

# VPC設定
variable "vpc_cidr" {
  description = "VPCのCIDRブロック"
  type        = string
  default     = "10.0.0.0/16"
}

variable "public_subnet_cidrs" {
  description = "パブリックサブネットのCIDR"
  type        = list(string)
  default     = ["10.0.1.0/24", "10.0.2.0/24"]
}

variable "private_subnet_cidrs" {
  description = "プライベートサブネットのCIDR（RDS用）"
  type        = list(string)
  default     = ["10.0.11.0/24", "10.0.12.0/24"]
}

variable "availability_zones" {
  description = "使用するAZ"
  type        = list(string)
  default     = ["us-east-2a", "us-east-2b"]
}

# EC2設定
variable "ec2_instance_type" {
  description = "EC2インスタンスタイプ"
  type        = string
  default     = "t3.micro"
}

variable "ec2_key_name" {
  description = "EC2用SSHキーペア名"
  type        = string
}

# RDS設定
variable "db_instance_class" {
  description = "RDSインスタンスクラス"
  type        = string
  default     = "db.t3.micro"
}

variable "db_name" {
  description = "データベース名"
  type        = string
  default     = "pickapp"
}

variable "db_username" {
  description = "DBマスターユーザー名"
  type        = string
  default     = "pickapp_admin"
}

variable "db_password" {
  description = "DBマスターパスワード"
  type        = string
  sensitive   = true
}

# アプリケーション設定（環境変数）
variable "openai_api_key" {
  description = "OpenAI APIキー"
  type        = string
  sensitive   = true
}

variable "line_channel_access_token" {
  description = "LINE Channel Access Token"
  type        = string
  sensitive   = true
}

variable "line_user_id" {
  description = "LINE User ID"
  type        = string
  sensitive   = true
}

variable "slack_webhook_url" {
  description = "Slack Webhook URL"
  type        = string
  sensitive   = true
}

variable "s3_bucket_name" {
  description = "S3バケット名"
  type        = string
  default     = "pickapp-articles"
}
