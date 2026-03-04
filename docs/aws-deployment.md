# PickApp - AWS デプロイガイド

EC2 (Amazon Linux 2023) + RDS (PostgreSQL) へのデプロイ手順です。

## 前提条件

- AWS アカウント
- AWS CLI がインストール・設定済み
- SSH キーペアを作成済み

## 1. VPC / ネットワーク構成

### 1.1 VPC作成

```bash
# VPC作成（CIDR: 10.0.0.0/16）
aws ec2 create-vpc \
  --cidr-block 10.0.0.0/16 \
  --tag-specifications 'ResourceType=vpc,Tags=[{Key=Name,Value=pickapp-vpc}]'
```

VPC IDをメモしておきます（例: `vpc-xxxxxxxxx`）

### 1.2 サブネット作成

```bash
# パブリックサブネット（EC2用）
aws ec2 create-subnet \
  --vpc-id vpc-xxxxxxxxx \
  --cidr-block 10.0.1.0/24 \
  --availability-zone ap-northeast-1a \
  --tag-specifications 'ResourceType=subnet,Tags=[{Key=Name,Value=pickapp-public-1a}]'

# プライベートサブネット（RDS用）- AZ-a
aws ec2 create-subnet \
  --vpc-id vpc-xxxxxxxxx \
  --cidr-block 10.0.10.0/24 \
  --availability-zone ap-northeast-1a \
  --tag-specifications 'ResourceType=subnet,Tags=[{Key=Name,Value=pickapp-private-1a}]'

# プライベートサブネット（RDS用）- AZ-c（RDSは2AZ必要）
aws ec2 create-subnet \
  --vpc-id vpc-xxxxxxxxx \
  --cidr-block 10.0.11.0/24 \
  --availability-zone ap-northeast-1c \
  --tag-specifications 'ResourceType=subnet,Tags=[{Key=Name,Value=pickapp-private-1c}]'
```

### 1.3 インターネットゲートウェイ

```bash
# IGW作成
aws ec2 create-internet-gateway \
  --tag-specifications 'ResourceType=internet-gateway,Tags=[{Key=Name,Value=pickapp-igw}]'

# VPCにアタッチ
aws ec2 attach-internet-gateway \
  --internet-gateway-id igw-xxxxxxxxx \
  --vpc-id vpc-xxxxxxxxx
```

### 1.4 ルートテーブル

```bash
# パブリックサブネット用ルートテーブル
aws ec2 create-route-table \
  --vpc-id vpc-xxxxxxxxx \
  --tag-specifications 'ResourceType=route-table,Tags=[{Key=Name,Value=pickapp-public-rt}]'

# インターネットへのルート追加
aws ec2 create-route \
  --route-table-id rtb-xxxxxxxxx \
  --destination-cidr-block 0.0.0.0/0 \
  --gateway-id igw-xxxxxxxxx

# パブリックサブネットに関連付け
aws ec2 associate-route-table \
  --route-table-id rtb-xxxxxxxxx \
  --subnet-id subnet-xxxxxxxxx
```

## 2. Security Group

### 2.1 EC2用セキュリティグループ

```bash
aws ec2 create-security-group \
  --group-name pickapp-ec2-sg \
  --description "Security group for PickApp EC2" \
  --vpc-id vpc-xxxxxxxxx

# SSH (22)
aws ec2 authorize-security-group-ingress \
  --group-id sg-xxxxxxxxx \
  --protocol tcp \
  --port 22 \
  --cidr YOUR_IP/32

# HTTP (80) - オプション
aws ec2 authorize-security-group-ingress \
  --group-id sg-xxxxxxxxx \
  --protocol tcp \
  --port 80 \
  --cidr 0.0.0.0/0

# アプリケーション (8000)
aws ec2 authorize-security-group-ingress \
  --group-id sg-xxxxxxxxx \
  --protocol tcp \
  --port 8000 \
  --cidr 0.0.0.0/0
```

### 2.2 RDS用セキュリティグループ

```bash
aws ec2 create-security-group \
  --group-name pickapp-rds-sg \
  --description "Security group for PickApp RDS" \
  --vpc-id vpc-xxxxxxxxx

# PostgreSQL (5432) - EC2からのみ
aws ec2 authorize-security-group-ingress \
  --group-id sg-yyyyyyyyy \
  --protocol tcp \
  --port 5432 \
  --source-group sg-xxxxxxxxx
```

## 3. RDS (PostgreSQL)

### 3.1 サブネットグループ作成

```bash
aws rds create-db-subnet-group \
  --db-subnet-group-name pickapp-db-subnet \
  --db-subnet-group-description "Subnet group for PickApp RDS" \
  --subnet-ids subnet-xxxxxxxxx subnet-yyyyyyyyy
```

### 3.2 RDSインスタンス作成

```bash
aws rds create-db-instance \
  --db-instance-identifier pickapp-db \
  --db-instance-class db.t3.micro \
  --engine postgres \
  --engine-version 15 \
  --master-username pickapp \
  --master-user-password YOUR_STRONG_PASSWORD \
  --allocated-storage 20 \
  --db-subnet-group-name pickapp-db-subnet \
  --vpc-security-group-ids sg-yyyyyyyyy \
  --no-publicly-accessible \
  --backup-retention-period 7 \
  --db-name pickapp
```

RDSエンドポイントをメモ（例: `pickapp-db.xxxxxxxxx.ap-northeast-1.rds.amazonaws.com`）

## 4. EC2

### 4.1 インスタンス作成

```bash
aws ec2 run-instances \
  --image-id ami-xxxxxxxxx \  # Amazon Linux 2023 AMI
  --instance-type t3.micro \
  --key-name your-key-pair \
  --security-group-ids sg-xxxxxxxxx \
  --subnet-id subnet-xxxxxxxxx \
  --associate-public-ip-address \
  --tag-specifications 'ResourceType=instance,Tags=[{Key=Name,Value=pickapp-server}]'
```

### 4.2 EC2にSSH接続

```bash
ssh -i your-key.pem ec2-user@EC2_PUBLIC_IP
```

### 4.3 Dockerインストール

```bash
# Docker インストール
sudo dnf update -y
sudo dnf install -y docker
sudo systemctl start docker
sudo systemctl enable docker
sudo usermod -aG docker ec2-user

# Docker Compose インストール
sudo curl -L "https://github.com/docker/compose/releases/latest/download/docker-compose-$(uname -s)-$(uname -m)" -o /usr/local/bin/docker-compose
sudo chmod +x /usr/local/bin/docker-compose

# 再ログインして docker グループを反映
exit
ssh -i your-key.pem ec2-user@EC2_PUBLIC_IP
```

### 4.4 アプリケーションデプロイ

```bash
# アプリケーションコードを配置
git clone https://github.com/your-repo/pickapp.git
cd pickapp

# 環境変数設定
cat > .env << EOF
ENVIRONMENT=production
DB_HOST=pickapp-db.xxxxxxxxx.ap-northeast-1.rds.amazonaws.com
DB_USER=pickapp
DB_PASSWORD=YOUR_STRONG_PASSWORD
DB_NAME=pickapp
OPENAI_API_KEY=sk-xxxxx
LINE_CHANNEL_ACCESS_TOKEN=xxxxx
LINE_USER_ID=Uxxxxx
SLACK_WEBHOOK_URL=https://hooks.slack.com/services/xxx/xxx/xxx
EOF

# 起動
docker-compose -f docker-compose.prod.yml up -d

# ログ確認
docker-compose -f docker-compose.prod.yml logs -f
```

## 5. 動作確認

```bash
# ヘルスチェック
curl http://EC2_PUBLIC_IP:8000/health

# 期待されるレスポンス
# {"status":"healthy"}
```

## 6. セキュリティ推奨事項

1. **SSH接続元を制限**: 自分のIPアドレスのみに限定
2. **HTTPS化**: ALBを追加してSSL終端
3. **環境変数**: AWS Systems Manager Parameter Store の使用を検討
4. **監視**: CloudWatch でログ・メトリクス監視を設定
5. **バックアップ**: RDSの自動バックアップを確認

## アーキテクチャ図

```
┌─────────────────────────────────────────────────────────────┐
│                          VPC                                 │
│  ┌────────────────────────┐  ┌────────────────────────────┐ │
│  │   Public Subnet        │  │   Private Subnet           │ │
│  │   (10.0.1.0/24)        │  │   (10.0.10.0/24)           │ │
│  │                        │  │                            │ │
│  │   ┌──────────────┐     │  │   ┌──────────────────┐     │ │
│  │   │     EC2      │     │  │   │       RDS        │     │ │
│  │   │   (Docker)   │────────────│   (PostgreSQL)   │     │ │
│  │   │              │     │  │   │                  │     │ │
│  │   └──────────────┘     │  │   └──────────────────┘     │ │
│  │          │             │  │                            │ │
│  └──────────│─────────────┘  └────────────────────────────┘ │
│             │                                               │
└─────────────│───────────────────────────────────────────────┘
              │
         ┌────┴────┐
         │   IGW   │
         └────┬────┘
              │
         Internet
              │
    ┌─────────┴─────────┐
    │   LINE / Slack    │
    │   OpenAI API      │
    └───────────────────┘
```
