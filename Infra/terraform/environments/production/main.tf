# 既存のRoute53ホストゾーン（Terraform管理外・参照のみ。
# ACM検証レコードとadminサブドメインの「追加」のみ行い、既存レコードには触れない）
data "aws_route53_zone" "main" {
  name = var.root_domain
}

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
  zone_id            = data.aws_route53_zone.main.zone_id
  image_uri          = var.api_image_uri
  app_bucket         = var.app_bucket
  drafts_table_name  = module.data.drafts_table_name
  drafts_table_arn   = module.data.drafts_table_arn
  ssm_parameter_arns = module.data.ssm_parameter_arns

  environment_variables = merge(local.common_lambda_env, {
    USER_ACCESS_KEY = data.aws_ssm_parameter.user_access_key.value
    ENCRYPT_SALT    = data.aws_ssm_parameter.encrypt_salt.value
  })
}

# バッチ: Lambda(batch-update / batch-create) + EventBridge Scheduler
module "batch" {
  source = "../../modules/batch"
  count  = var.api_image_uri != "" && var.batch_create_image_uri != "" ? 1 : 0

  update_image_uri   = var.api_image_uri # apiと同一イメージ・ハンドラ指定のみ変更
  create_image_uri   = var.batch_create_image_uri
  app_bucket         = var.app_bucket
  drafts_table_arn   = module.data.drafts_table_arn
  ssm_parameter_arns = module.data.ssm_parameter_arns
  scheduler_state    = var.scheduler_state

  environment_variables = merge(local.common_lambda_env, {
    POLIS_LOGIN_USER     = data.aws_ssm_parameter.polis_login_user.value
    POLIS_LOGIN_PASSWORD = data.aws_ssm_parameter.polis_login_password.value
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
  zone_id         = data.aws_route53_zone.main.zone_id
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

data "aws_ssm_parameter" "openai_api_key" {
  name       = module.data.ssm_parameter_names["openai-api-key"]
  depends_on = [module.data]
}

data "aws_ssm_parameter" "langsmith_api_key" {
  name       = module.data.ssm_parameter_names["langsmith-api-key"]
  depends_on = [module.data]
}

data "aws_ssm_parameter" "batch_access_key" {
  name       = module.data.ssm_parameter_names["batch-access-key"]
  depends_on = [module.data]
}

data "aws_ssm_parameter" "user_access_key" {
  name       = module.data.ssm_parameter_names["user-access-key"]
  depends_on = [module.data]
}

data "aws_ssm_parameter" "encrypt_salt" {
  name       = module.data.ssm_parameter_names["encrypt-salt"]
  depends_on = [module.data]
}

data "aws_ssm_parameter" "polis_login_user" {
  name       = module.data.ssm_parameter_names["polis-login-user"]
  depends_on = [module.data]
}

data "aws_ssm_parameter" "polis_login_password" {
  name       = module.data.ssm_parameter_names["polis-login-password"]
  depends_on = [module.data]
}

locals {
  common_lambda_env = {
    APP_ENV            = "serverless"
    API_BASE_URL       = "https://${var.api_domain}/"
    CLIENT_BASE_URL    = var.client_base_url
    CORS_ALLOW_ORIGINS = join(",", var.cors_allow_origins)
    ADMIN_ALLOW_IPS    = join(",", var.admin_allow_ips)
    DRAFTS_TABLE       = module.data.drafts_table_name
    BATCH_ACCESS_KEY   = data.aws_ssm_parameter.batch_access_key.value
    OPENAI_API_KEY     = data.aws_ssm_parameter.openai_api_key.value
    LANGCHAIN_API_KEY  = data.aws_ssm_parameter.langsmith_api_key.value
    LANGCHAIN_ENDPOINT = "https://api.smith.langchain.com"
  }
}
