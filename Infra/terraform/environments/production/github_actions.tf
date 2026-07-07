# ============================================================
# GitHub Actions デプロイ用 OIDC + IAMロール
#
# パブリックリポジトリからのセキュアな自動デプロイのため、長期アクセスキーを
# GitHub Secretsに置かず、OIDCフェデレーションで一時クレデンシャルを払い出す。
# Assumeできるのは PolisJAPAN/PolisJAPAN の main ブランチ上のワークフローのみ
# （フォークはsubが別リポジトリ名になるためAssume不可）。
# ============================================================

data "aws_caller_identity" "gha" {}

resource "aws_iam_openid_connect_provider" "github_actions" {
  url            = "https://token.actions.githubusercontent.com"
  client_id_list = ["sts.amazonaws.com"]
  # AWSは2023年以降GitHub OIDCの証明書検証にthumbprintを使用しないが、必須項目のため既知値を設定
  thumbprint_list = ["6938fd4d98bab03faadb97b34396831e3780aea1"]
}

locals {
  gha_account_id = data.aws_caller_identity.gha.account_id
  gha_region     = "ap-northeast-3" # providers.tf と一致させる
  gha_main_sub   = "repo:PolisJAPAN/PolisJAPAN:ref:refs/heads/main"

  # クライアントの同期先バケットと無効化対象ディストリビューション
  gha_static_buckets = ["pol-is.jp", "app.pol-is.jp", var.admin_domain]
  gha_distribution_arns = [
    "arn:aws:cloudfront::${local.gha_account_id}:distribution/E1L9GH70CTWAY6", # LP
    "arn:aws:cloudfront::${local.gha_account_id}:distribution/${var.csv_cloudfront_distribution_id}", # app
    "arn:aws:cloudfront::${local.gha_account_id}:distribution/${module.admin_site.distribution_id}",  # admin
  ]

  gha_lambda_arns = [
    "arn:aws:lambda:${local.gha_region}:${local.gha_account_id}:function:polisjapan-api",
    "arn:aws:lambda:${local.gha_region}:${local.gha_account_id}:function:polisjapan-batch-update",
    "arn:aws:lambda:${local.gha_region}:${local.gha_account_id}:function:polisjapan-batch-create",
  ]
  gha_ecr_arns = [
    "arn:aws:ecr:${local.gha_region}:${local.gha_account_id}:repository/polisjapan-api",
    "arn:aws:ecr:${local.gha_region}:${local.gha_account_id}:repository/polisjapan-batch-create",
  ]
}

data "aws_iam_policy_document" "gha_assume" {
  statement {
    actions = ["sts:AssumeRoleWithWebIdentity"]

    principals {
      type        = "Federated"
      identifiers = [aws_iam_openid_connect_provider.github_actions.arn]
    }

    condition {
      test     = "StringEquals"
      variable = "token.actions.githubusercontent.com:aud"
      values   = ["sts.amazonaws.com"]
    }

    condition {
      test     = "StringEquals"
      variable = "token.actions.githubusercontent.com:sub"
      values   = [local.gha_main_sub]
    }
  }
}

# ---- クライアントデプロイ用（S3 sync + CloudFront無効化のみ） ----

resource "aws_iam_role" "gha_deploy_client" {
  name               = "polisjapan-gha-deploy-client"
  description        = "GitHub Actions deploy-client.yml (static site sync)"
  assume_role_policy = data.aws_iam_policy_document.gha_assume.json
}

resource "aws_iam_role_policy" "gha_deploy_client" {
  name = "deploy-client"
  role = aws_iam_role.gha_deploy_client.id

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Sid      = "ListBuckets"
        Effect   = "Allow"
        Action   = ["s3:ListBucket"]
        Resource = [for b in local.gha_static_buckets : "arn:aws:s3:::${b}"]
      },
      {
        Sid      = "SyncObjects"
        Effect   = "Allow"
        Action   = ["s3:PutObject", "s3:DeleteObject"]
        Resource = [for b in local.gha_static_buckets : "arn:aws:s3:::${b}/*"]
      },
      {
        # csv/* はバッチLambdaが管理する本番データ。ワークフローの--exclude漏れに対する防波堤
        Sid      = "DenyCsvOverwrite"
        Effect   = "Deny"
        Action   = ["s3:PutObject", "s3:DeleteObject"]
        Resource = "arn:aws:s3:::app.pol-is.jp/csv/*"
      },
      {
        Sid      = "InvalidateCaches"
        Effect   = "Allow"
        Action   = ["cloudfront:CreateInvalidation"]
        Resource = local.gha_distribution_arns
      },
    ]
  })
}

# ---- サーバーデプロイ用（ECR push + Lambdaイメージ切り替えのみ） ----

resource "aws_iam_role" "gha_deploy_server" {
  name               = "polisjapan-gha-deploy-server"
  description        = "GitHub Actions deploy-server.yml (Lambda image deploy)"
  assume_role_policy = data.aws_iam_policy_document.gha_assume.json
}

resource "aws_iam_role_policy" "gha_deploy_server" {
  name = "deploy-server"
  role = aws_iam_role.gha_deploy_server.id

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Sid      = "EcrAuth"
        Effect   = "Allow"
        Action   = ["ecr:GetAuthorizationToken"]
        Resource = "*"
      },
      {
        Sid    = "EcrPush"
        Effect = "Allow"
        Action = [
          "ecr:BatchCheckLayerAvailability",
          "ecr:BatchGetImage",
          "ecr:GetDownloadUrlForLayer",
          "ecr:InitiateLayerUpload",
          "ecr:UploadLayerPart",
          "ecr:CompleteLayerUpload",
          "ecr:PutImage",
        ]
        Resource = local.gha_ecr_arns
      },
      {
        Sid    = "UpdateLambda"
        Effect = "Allow"
        Action = [
          "lambda:UpdateFunctionCode",
          "lambda:GetFunction",
          "lambda:GetFunctionConfiguration",
        ]
        Resource = local.gha_lambda_arns
      },
    ]
  })
}

output "gha_deploy_client_role_arn" {
  description = "deploy-client.yml の role-to-assume に設定するARN"
  value       = aws_iam_role.gha_deploy_client.arn
}

output "gha_deploy_server_role_arn" {
  description = "deploy-server.yml の role-to-assume に設定するARN"
  value       = aws_iam_role.gha_deploy_server.arn
}
