# ============================================================
# バッチ: Lambda(batch-update / batch-create) + EventBridge Scheduler
# Schedulerはカットオーバーまで DISABLED（旧cronとの二重実行防止）
# ============================================================

locals {
  functions = {
    update = {
      name        = "polisjapan-batch-update"
      image_uri   = var.update_image_uri
      handler     = "api.lambda_handlers.batch_update.handler"
      memory      = 512
      timeout     = 900
      schedule    = "rate(5 minutes)"
      description = "投票情報の取得とCSV更新"
    }
    create = {
      name        = "polisjapan-batch-create"
      image_uri   = var.create_image_uri
      handler     = "api.lambda_handlers.batch_create.handler"
      memory      = 2048
      timeout     = 900
      schedule    = "rate(15 minutes)"
      description = "承認済み下書きのPolisへの公開（1起動1件）"
    }
  }
}

resource "aws_cloudwatch_log_group" "batch" {
  for_each          = local.functions
  name              = "/aws/lambda/${each.value.name}"
  retention_in_days = 30
}

resource "aws_iam_role" "batch" {
  for_each = local.functions
  name     = "${each.value.name}-role"

  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Effect    = "Allow"
      Principal = { Service = "lambda.amazonaws.com" }
      Action    = "sts:AssumeRole"
    }]
  })
}

resource "aws_iam_role_policy" "batch" {
  for_each = local.functions
  name     = "${each.value.name}-policy"
  role     = aws_iam_role.batch[each.key].id

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Sid      = "Logs"
        Effect   = "Allow"
        Action   = ["logs:CreateLogStream", "logs:PutLogEvents"]
        Resource = "${aws_cloudwatch_log_group.batch[each.key].arn}:*"
      },
      {
        Sid    = "CsvBucket"
        Effect = "Allow"
        Action = ["s3:GetObject", "s3:PutObject", "s3:DeleteObject", "s3:ListBucket"]
        Resource = concat(
          ["arn:aws:s3:::${var.app_bucket}", "arn:aws:s3:::${var.app_bucket}/*"],
          var.extra_bucket_arns,
        )
      },
      {
        Sid    = "Drafts"
        Effect = "Allow"
        Action = [
          "dynamodb:GetItem", "dynamodb:PutItem", "dynamodb:UpdateItem",
          "dynamodb:Query", "dynamodb:Scan"
        ]
        Resource = [var.drafts_table_arn, "${var.drafts_table_arn}/index/*"]
      },
      {
        Sid      = "Secrets"
        Effect   = "Allow"
        Action   = ["ssm:GetParameter", "ssm:GetParameters"]
        Resource = var.ssm_parameter_arns
      },
    ]
  })
}

resource "aws_lambda_function" "batch" {
  for_each = local.functions

  function_name = each.value.name
  description   = each.value.description
  role          = aws_iam_role.batch[each.key].arn
  package_type  = "Image"
  image_uri     = each.value.image_uri
  timeout       = each.value.timeout
  memory_size   = each.value.memory
  architectures = ["x86_64"]

  # 多重起動を防止（前回実行が長引いた場合に並走させない）
  reserved_concurrent_executions = 1

  image_config {
    command = [each.value.handler]
  }

  environment {
    variables = var.environment_variables
  }

  # イメージの更新はGitHub Actions（deploy-server.yml）が update-function-code で行うため、
  # Terraformはimage_uriの差分を無視する（applyでCIのデプロイを巻き戻さない）。初回作成時のみtfvarsの値を使用
  lifecycle {
    ignore_changes = [image_uri]
  }

  depends_on = [aws_cloudwatch_log_group.batch]
}

# ---- EventBridge Scheduler ----

resource "aws_iam_role" "scheduler" {
  name = "polisjapan-scheduler-invoke"

  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Effect    = "Allow"
      Principal = { Service = "scheduler.amazonaws.com" }
      Action    = "sts:AssumeRole"
    }]
  })
}

resource "aws_iam_role_policy" "scheduler" {
  name = "polisjapan-scheduler-invoke"
  role = aws_iam_role.scheduler.id

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Effect   = "Allow"
      Action   = "lambda:InvokeFunction"
      Resource = [for f in aws_lambda_function.batch : f.arn]
    }]
  })
}

resource "aws_scheduler_schedule" "batch" {
  for_each = local.functions

  name                = "${each.value.name}-schedule"
  schedule_expression = each.value.schedule
  state               = var.scheduler_state

  flexible_time_window {
    mode = "OFF"
  }

  target {
    arn      = aws_lambda_function.batch[each.key].arn
    role_arn = aws_iam_role.scheduler.arn

    retry_policy {
      maximum_retry_attempts = 0 # 失敗時は次回スケジュールに委ねる（重複実行防止）
    }
  }
}
