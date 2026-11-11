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

# ---- 投稿バッチ(batch-create)の滞留アラーム ----
# メトリクスは batch-create が起動のたびにEMFで出力する
# （Server/web/api/lambda_handlers/backlog_monitor.py）。
# Errorsアラームは失敗下書きがFAILEDに隔離されるとすぐOKに戻るため、
# 「解消するまでALARMのまま」になる件数ベースのアラームで補う
# （2026-10に45件・約4週間の滞留を見逃した再発防止）。

locals {
  backlog_namespace  = "PolisJAPAN/Batch"
  backlog_dimensions = { FunctionName = "polisjapan-batch-create" }
}

# 投稿失敗(FAILED)の下書きが1件でも残っている間はALARM
resource "aws_cloudwatch_metric_alarm" "publish_failed_drafts" {
  count = var.enable_publish_backlog_alarms ? 1 : 0

  alarm_name          = "polisjapan-batch-create-failed-drafts"
  alarm_description   = "Polisへの投稿に失敗して隔離された下書き(FAILED)が残っている。原因を解消し、管理画面で再承認するまで投稿されない"
  namespace           = local.backlog_namespace
  metric_name         = "FailedDrafts"
  dimensions          = local.backlog_dimensions
  statistic           = "Maximum"
  period              = 1800
  evaluation_periods  = 1
  threshold           = 1
  comparison_operator = "GreaterThanOrEqualToThreshold"
  # 報告の途絶は no-report アラームが担当。ここでは状態を維持してフラップさせない
  treat_missing_data = "ignore"

  alarm_actions = [aws_sns_topic.alerts.arn]
  ok_actions    = [aws_sns_topic.alerts.arn]
}

# 投稿待ち(APPROVED)があるのに2時間1件も投稿できていない
# （隔離の対象外の失敗=CSV/S3/ストア更新の失敗が続くケースを拾う）
resource "aws_cloudwatch_metric_alarm" "publish_stalled" {
  count = var.enable_publish_backlog_alarms ? 1 : 0

  alarm_name          = "polisjapan-batch-create-stalled"
  alarm_description   = "投稿待ちの下書きがあるのに2時間1件もPolisへ投稿できていない"
  evaluation_periods  = 1
  threshold           = 1
  comparison_operator = "GreaterThanOrEqualToThreshold"
  treat_missing_data  = "ignore"

  metric_query {
    id          = "stalled"
    expression  = "IF(pending >= 1 AND published < 1, 1, 0)"
    label       = "投稿待ちあり かつ 投稿0件"
    return_data = true
  }

  metric_query {
    id = "pending"
    metric {
      namespace   = local.backlog_namespace
      metric_name = "PendingDrafts"
      dimensions  = local.backlog_dimensions
      stat        = "Minimum"
      period      = 7200
    }
  }

  metric_query {
    id = "published"
    metric {
      namespace   = local.backlog_namespace
      metric_name = "PublishedDrafts"
      dimensions  = local.backlog_dimensions
      stat        = "Sum"
      period      = 7200
    }
  }

  alarm_actions = [aws_sns_topic.alerts.arn]
  ok_actions    = [aws_sns_topic.alerts.arn]
}

# batch-createからの報告が1時間途絶えた（スケジューラ停止・起動不能など）
resource "aws_cloudwatch_metric_alarm" "publish_no_report" {
  count = var.enable_publish_backlog_alarms ? 1 : 0

  alarm_name          = "polisjapan-batch-create-no-report"
  alarm_description   = "batch-createの滞留状況の報告が1時間途絶えた（15分間隔で届くはず）。スケジューラ停止やLambda起動不能の可能性"
  namespace           = local.backlog_namespace
  metric_name         = "PendingDrafts"
  dimensions          = local.backlog_dimensions
  statistic           = "SampleCount"
  period              = 3600
  evaluation_periods  = 1
  threshold           = 1
  comparison_operator = "LessThanThreshold"
  treat_missing_data  = "breaching"

  alarm_actions = [aws_sns_topic.alerts.arn]
  ok_actions    = [aws_sns_topic.alerts.arn]
}
