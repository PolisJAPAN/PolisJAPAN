# ============================================================
# API: Lambda(api, FastAPI+Mangum) + API Gateway HTTP API + ACM
# カスタムドメインは作成するが、Route53のapi.pol-is.jpレコードは
# 切り替えない（カットオーバーRunbookで手動切替）
# ============================================================

# ---- ACM証明書（API GWリージョナル用: ap-northeast-3） ----

resource "aws_acm_certificate" "api" {
  domain_name       = var.api_domain
  validation_method = "DNS"

  lifecycle {
    create_before_destroy = true
  }
}

resource "aws_route53_record" "api_cert_validation" {
  for_each = {
    for dvo in aws_acm_certificate.api.domain_validation_options : dvo.domain_name => {
      name   = dvo.resource_record_name
      record = dvo.resource_record_value
      type   = dvo.resource_record_type
    }
  }

  zone_id = var.zone_id
  name    = each.value.name
  type    = each.value.type
  ttl     = 300
  records = [each.value.record]
}

resource "aws_acm_certificate_validation" "api" {
  certificate_arn         = aws_acm_certificate.api.arn
  validation_record_fqdns = [for r in aws_route53_record.api_cert_validation : r.fqdn]
}

# ---- Lambda ----

data "aws_caller_identity" "current" {}

resource "aws_cloudwatch_log_group" "api" {
  name              = "/aws/lambda/polisjapan-api"
  retention_in_days = 30
}

resource "aws_iam_role" "api" {
  name = "polisjapan-lambda-api"

  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Effect    = "Allow"
      Principal = { Service = "lambda.amazonaws.com" }
      Action    = "sts:AssumeRole"
    }]
  })
}

resource "aws_iam_role_policy" "api" {
  name = "polisjapan-lambda-api"
  role = aws_iam_role.api.id

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Sid      = "Logs"
        Effect   = "Allow"
        Action   = ["logs:CreateLogStream", "logs:PutLogEvents"]
        Resource = "${aws_cloudwatch_log_group.api.arn}:*"
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
      {
        # テーマ削除時のピンポイント無効化用（削除はCache-ControlのTTLでは反映できないため）
        Sid      = "DeleteInvalidation"
        Effect   = "Allow"
        Action   = ["cloudfront:CreateInvalidation"]
        Resource = "arn:aws:cloudfront::${data.aws_caller_identity.current.account_id}:distribution/${var.cloudfront_distribution_id}"
      },
    ]
  })
}

resource "aws_lambda_function" "api" {
  function_name = "polisjapan-api"
  role          = aws_iam_role.api.arn
  package_type  = "Image"
  image_uri     = var.image_uri
  timeout       = 120
  memory_size   = 1024
  architectures = ["x86_64"]

  image_config {
    command = ["api.main.handler"]
  }

  environment {
    variables = var.environment_variables
  }

  depends_on = [aws_cloudwatch_log_group.api]
}

# ---- API Gateway (HTTP API) ----

resource "aws_apigatewayv2_api" "api" {
  name          = "polisjapan-api"
  protocol_type = "HTTP"
}

resource "aws_apigatewayv2_integration" "lambda" {
  api_id                 = aws_apigatewayv2_api.api.id
  integration_type       = "AWS_PROXY"
  integration_uri        = aws_lambda_function.api.invoke_arn
  payload_format_version = "2.0"
}

resource "aws_apigatewayv2_route" "default" {
  api_id    = aws_apigatewayv2_api.api.id
  route_key = "$default"
  target    = "integrations/${aws_apigatewayv2_integration.lambda.id}"
}

resource "aws_apigatewayv2_stage" "default" {
  api_id      = aws_apigatewayv2_api.api.id
  name        = "$default"
  auto_deploy = true
}

resource "aws_lambda_permission" "apigw" {
  statement_id  = "AllowAPIGatewayInvoke"
  action        = "lambda:InvokeFunction"
  function_name = aws_lambda_function.api.function_name
  principal     = "apigateway.amazonaws.com"
  source_arn    = "${aws_apigatewayv2_api.api.execution_arn}/*/*"
}

# ---- カスタムドメイン（DNS切替まではトラフィックなし） ----

resource "aws_apigatewayv2_domain_name" "api" {
  domain_name = var.api_domain

  domain_name_configuration {
    certificate_arn = aws_acm_certificate_validation.api.certificate_arn
    endpoint_type   = "REGIONAL"
    security_policy = "TLS_1_2"
  }
}

resource "aws_apigatewayv2_api_mapping" "api" {
  api_id      = aws_apigatewayv2_api.api.id
  domain_name = aws_apigatewayv2_domain_name.api.id
  stage       = aws_apigatewayv2_stage.default.id
}
