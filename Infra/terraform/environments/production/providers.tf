provider "aws" {
  region  = "ap-northeast-3"
  profile = var.aws_profile

  default_tags {
    tags = {
      Project   = "PolisJAPAN"
      ManagedBy = "terraform"
    }
  }
}

# CloudFront用ACM証明書・Route53ヘルスチェックのアラームはus-east-1に置く必要がある
provider "aws" {
  alias   = "us_east_1"
  region  = "us-east-1"
  profile = var.aws_profile

  default_tags {
    tags = {
      Project   = "PolisJAPAN"
      ManagedBy = "terraform"
    }
  }
}
