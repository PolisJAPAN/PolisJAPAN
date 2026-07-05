terraform {
  required_version = ">= 1.10"

  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 6.0" # python3.14ランタイム対応のためv6系（v5はLambda runtime検証リストが古い）
    }
  }

  # tfstateはS3で管理（S3ネイティブロック使用、DynamoDBロックテーブル不要）
  # バケットは初回のみ手動作成する（Infra/terraform/README.md の Bootstrap 参照）
  backend "s3" {
    bucket = "polisjapan-tfstate"
    key    = "production/terraform.tfstate"
    region = "ap-northeast-3"
    # backendはproviderのprofile設定を継承しないため明示する
    # （未指定だとinit/state操作がデフォルト認証チェーンで実行されてしまう）
    profile      = "terraform"
    use_lockfile = true
    encrypt      = true
  }
}
