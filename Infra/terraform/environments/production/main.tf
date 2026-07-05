# Route53ホストゾーンは route53.tf でTerraform管理（import済み）

# データ層: DynamoDB / アーカイブS3 / ECR / SSMパラメータ
module "data" {
  source = "../../modules/data"
}

# API: Lambda(api) + API Gateway + ACM + カスタムドメイン
# コンテナイメージのpush後（api_image_uri指定後）に作成される
module "api" {
  source = "../../modules/api"
  count  = var.api_image_uri != "" ? 1 : 0

  api_domain         = var.api_domain
  zone_id            = aws_route53_zone.main.zone_id
  image_uri          = var.api_image_uri
  app_bucket         = var.app_bucket
  extra_bucket_arns  = local.extra_bucket_arns
  drafts_table_name  = module.data.drafts_table_name
  drafts_table_arn   = module.data.drafts_table_arn
  ssm_parameter_arns = module.data.ssm_parameter_arns

  environment_variables      = local.common_lambda_env
  cloudfront_distribution_id = var.csv_cloudfront_distribution_id
}

# バッチ: Lambda(batch-update / batch-create) + EventBridge Scheduler
module "batch" {
  source = "../../modules/batch"
  count  = var.api_image_uri != "" && var.batch_create_image_uri != "" ? 1 : 0

  update_image_uri   = var.api_image_uri # apiと同一イメージ・ハンドラ指定のみ変更
  create_image_uri   = var.batch_create_image_uri
  app_bucket         = var.app_bucket
  extra_bucket_arns  = local.extra_bucket_arns
  drafts_table_arn   = module.data.drafts_table_arn
  ssm_parameter_arns = module.data.ssm_parameter_arns
  scheduler_state    = var.scheduler_state

  environment_variables = merge(local.common_lambda_env, {
    POLIS_LOGIN_USER     = data.aws_ssm_parameter.secrets["polis-login-user"].value
    POLIS_LOGIN_PASSWORD = data.aws_ssm_parameter.secrets["polis-login-password"].value
  })
}

# 管理画面: S3 + CloudFront + CloudFront Function(IP制限)
module "admin_site" {
  source = "../../modules/admin-site"
  providers = {
    aws           = aws
    aws.us_east_1 = aws.us_east_1
  }

  admin_domain    = var.admin_domain
  zone_id         = aws_route53_zone.main.zone_id
  admin_allow_ips = var.admin_allow_ips
}

# 監視: Route53ヘルスチェック + アラーム + SNS通知
module "monitoring" {
  source = "../../modules/monitoring"
  providers = {
    aws           = aws
    aws.us_east_1 = aws.us_east_1
  }

  api_domain          = var.api_domain
  alert_email         = var.alert_email
  enable_health_check = var.enable_health_check
  lambda_function_names = concat(
    length(module.api) > 0 ? [module.api[0].function_name] : [],
    length(module.batch) > 0 ? module.batch[0].function_names : [],
  )
}

# ------------------------------------------------------------
# Lambda共通の環境変数
# シークレットはSSM(SecureString)を情報源とし、値の手動投入後に
# terraform apply で環境変数へ反映される（tfstateに値が含まれる点は
# README のセキュリティ注記を参照）
# ------------------------------------------------------------

data "aws_ssm_parameter" "secrets" {
  for_each = module.data.ssm_parameter_names

  name       = each.value
  depends_on = [module.data]

  lifecycle {
    # SSM投入忘れのままLambda環境変数にプレースホルダを配ってしまう事故を防ぐ
    # （Lambda系リソース作成時 = 第2段階apply でのみ評価される）
    postcondition {
      condition     = !(var.api_image_uri != "" && self.value == "CHANGEME")
      error_message = "SSMパラメータ ${self.name} が初期値(CHANGEME)のままです。aws ssm put-parameter --overwrite で実値を投入してから再実行してください。"
    }
  }
}

locals {
  # E2Eサンドボックスバケットが指定されていればIAM許可対象に加える
  extra_bucket_arns = var.e2e_sandbox_bucket != "" ? [
    "arn:aws:s3:::${var.e2e_sandbox_bucket}",
    "arn:aws:s3:::${var.e2e_sandbox_bucket}/*",
  ] : []

  # 注意: serverless設定(configs/serverless/constants.py)の必須キー
  # (API_BASE_URL/CLIENT_BASE_URL/ENCRYPT_SALT/BATCH_ACCESS_KEY/USER_ACCESS_KEY)は
  # api・batch全Lambdaが設定読込時に参照するため、必ずこの共通envに含めること
  common_lambda_env = {
    APP_ENV                 = "serverless"
    CSV_BUCKET              = var.app_bucket
    API_BASE_URL            = "https://${var.api_domain}/"
    CLIENT_BASE_URL         = var.client_base_url
    CORS_ALLOW_ORIGINS      = join(",", var.cors_allow_origins)
    ADMIN_ALLOW_IPS         = join(",", var.admin_allow_ips)
    DRAFTS_TABLE            = module.data.drafts_table_name
    CLOUDFRONT_DISTRIBUTION = var.csv_cloudfront_distribution_id
    ENCRYPT_SALT            = data.aws_ssm_parameter.secrets["encrypt-salt"].value
    BATCH_ACCESS_KEY        = data.aws_ssm_parameter.secrets["batch-access-key"].value
    USER_ACCESS_KEY         = data.aws_ssm_parameter.secrets["user-access-key"].value
    OPENAI_API_KEY          = data.aws_ssm_parameter.secrets["openai-api-key"].value
    LANGCHAIN_API_KEY       = data.aws_ssm_parameter.secrets["langsmith-api-key"].value
    LANGCHAIN_ENDPOINT      = "https://api.smith.langchain.com"
  }
}
