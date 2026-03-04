# PickApp - Terraform AWS Infrastructure
# Provider設定

terraform {
  required_version = ">= 1.0.0"

  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 5.0"
    }
  }
}

provider "aws" {
  region = var.aws_region

  default_tags {
    tags = {
      Project     = "pickapp"
      Environment = var.environment
      ManagedBy   = "terraform"
    }
  }
}
