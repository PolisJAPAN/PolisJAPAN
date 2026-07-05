# ============================================================
# 監視: Route53ヘルスチェック + CloudWatchアラーム + SNSメール通知
# - Synthetics Canary($31/月)の代替（$0.50/月）
# - バッチLambdaの失敗検知（現行構成にはない検知能力）
# - Route53ヘルスチェックのメトリクスはus-east-1にのみ出るため、
#   その通知用SNS/アラームはus-east-1に置く
# ============================================================

terraform {
  required_providers {
    aws = {
      source                = "hashicorp/aws"
      configuration_aliases = [aws.us_east_1]
    }
  }
}

# ---- 通知先SNS（各リージョン） ----

resource "aws_sns_topic" "alerts" {
  name = "polisjapan-alerts"
}

resource "aws_sns_topic_subscription" "alerts_email" {
  topic_arn = aws_sns_topic.alerts.arn
  protocol  = "email"
  endpoint  = var.alert_email
}

resource "aws_sns_topic" "alerts_us" {
  provider = aws.us_east_1
  name     = "polisjapan-alerts"
}

resource "aws_sns_topic_subscription" "alerts_us_email" {
  provider  = aws.us_east_1
  topic_arn = aws_sns_topic.alerts_us.arn
  protocol  = "email"
  endpoint  = var.alert_email
}

# ---- Route53ヘルスチェック（HTTPS検証込み = 証明書失効も検知できる） ----

resource "aws_route53_health_check" "api" {
  count = var.enable_health_check ? 1 : 0

  fqdn              = var.api_domain
  type              = "HTTPS"
  port              = 443
  resource_path     = "/batch/healthcheck"
  request_interval  = 30
  failure_threshold = 3

  tags = {
    Name = "polisjapan-api-healthcheck"
  }
}

resource "aws_cloudwatch_metric_alarm" "health_check" {
  count    = var.enable_health_check ? 1 : 0
  provider = aws.us_east_1

  alarm_name          = "polisjapan-api-healthcheck-failed"
  alarm_description   = "api.pol-is.jp のヘルスチェック失敗（HTTPSエラー・証明書失効を含む）"
  namespace           = "AWS/Route53"
  metric_name         = "HealthCheckStatus"
  statistic           = "Minimum"
  period              = 60
  evaluation_periods  = 3
  threshold           = 1
  comparison_operator = "LessThanThreshold"
  treat_missing_data  = "breaching"

  dimensions = {
    HealthCheckId = aws_route53_health_check.api[0].id
  }

  alarm_actions = [aws_sns_topic.alerts_us.arn]
  ok_actions    = [aws_sns_topic.alerts_us.arn]
}

# ---- Lambdaエラーアラーム（api・バッチ共通） ----

resource "aws_cloudwatch_metric_alarm" "lambda_errors" {
  for_each = toset(var.lambda_function_names)

  alarm_name          = "${each.value}-errors"
  alarm_description   = "${each.value} の実行エラー"
  namespace           = "AWS/Lambda"
  metric_name         = "Errors"
  statistic           = "Sum"
  period              = 300
  evaluation_periods  = 1
  threshold           = 1
  comparison_operator = "GreaterThanOrEqualToThreshold"
  treat_missing_data  = "notBreaching"

  dimensions = {
    FunctionName = each.value
  }

  alarm_actions = [aws_sns_topic.alerts.arn]
  ok_actions    = [aws_sns_topic.alerts.arn]
}
