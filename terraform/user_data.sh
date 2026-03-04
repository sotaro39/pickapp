#!/bin/bash
set -e

# ログ出力
exec > >(tee /var/log/user-data.log) 2>&1
echo "=== PickApp Setup Started: $(date) ==="

# システム更新
dnf update -y

# Docker インストール
dnf install -y docker git
systemctl start docker
systemctl enable docker

# Docker Compose インストール
curl -L "https://github.com/docker/compose/releases/latest/download/docker-compose-$(uname -s)-$(uname -m)" -o /usr/local/bin/docker-compose
chmod +x /usr/local/bin/docker-compose

# ec2-user を docker グループに追加
usermod -aG docker ec2-user

# アプリケーションディレクトリ作成
mkdir -p /opt/pickapp
cd /opt/pickapp

# 環境変数ファイル作成
cat > .env << 'EOF'
ENVIRONMENT=production
DATABASE_URL=postgresql+asyncpg://${db_username}:${db_password}@${db_host}:5432/${db_name}
OPENAI_API_KEY=${openai_api_key}
LINE_CHANNEL_ACCESS_TOKEN=${line_channel_access_token}
LINE_USER_ID=${line_user_id}
SLACK_WEBHOOK_URL=${slack_webhook_url}
S3_BUCKET_NAME=${s3_bucket_name}
AWS_DEFAULT_REGION=${aws_region}
EOF

# docker-compose.yml 作成（本番用）
cat > docker-compose.yml << 'COMPOSE'
version: '3.8'

services:
  app:
    image: pickapp:latest
    build:
      context: .
      dockerfile: Dockerfile
    container_name: pickapp-app
    ports:
      - "80:8000"
    env_file:
      - .env
    environment:
      - TZ=Asia/Tokyo
    restart: always
    healthcheck:
      test: ["CMD", "curl", "-f", "http://localhost:8000/api/health"]
      interval: 30s
      timeout: 10s
      retries: 3

networks:
  default:
    name: pickapp-network
COMPOSE

# 権限設定
chown -R ec2-user:ec2-user /opt/pickapp

echo "=== PickApp Setup Completed: $(date) ==="
echo "Next: Clone your repository and run 'docker-compose up -d'"
