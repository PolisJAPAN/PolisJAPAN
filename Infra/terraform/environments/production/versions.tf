terraform {
  required_version = ">= 1.10"

  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 5.80"
    }
  }

  # tfstateはS3で管理（S3ネイティブロック使用、DynamoDBロックテーブル不要）
  # バケットは初回のみ手動作成する（Infra/terraform/README.md の Bootstrap 参照）
  backend "s3" {
    bucket       = "polisjapan-tfstate"
    key          = "production/terraform.tfstate"
    region       = "ap-northeast-3"
    use_lockfile = true
    encrypt      = true
  }
}
