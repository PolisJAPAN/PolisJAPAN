# ============================================================
# 既存のcontact/share系（us-east-1・手動作成）のTerraform取り込み
# - Lambda: インフラ属性のみ管理（コードはデプロイ済みのものを維持=ignore_changes）
# - API Gateway: REST API本体とステージのみ管理。
#   メソッド/統合定義・IAMサービスロールは凍結済みレガシーとして意図的に管理外
#   （bodyを指定しないため、Terraformが子リソースに触れることはない）
# ============================================================

import {
  to = aws_lambda_function.contact
  id = "PolisJAPAN-Contact"
}

import {
  to = aws_lambda_function.share_ogp
  id = "PolisJAPAN-GetOGP"
}

import {
  to = aws_cloudwatch_log_group.contact
  id = "/aws/lambda/PolisJAPAN-Contact"
}

import {
  to = aws_cloudwatch_log_group.share_ogp
  id = "/aws/lambda/PolisJAPAN-GetOGP"
}

import {
  to = aws_api_gateway_rest_api.contact
  id = "7r1e9gjfmk"
}

import {
  to = aws_api_gateway_rest_api.share
  id = "jh9u2wjvea"
}

import {
  to = aws_api_gateway_stage.contact
  id = "7r1e9gjfmk/production"
}

import {
  to = aws_api_gateway_stage.share
  id = "jh9u2wjvea/Production"
}

# ---- Lambda ----

resource "aws_lambda_function" "contact" {
  provider      = aws.us_east_1
  function_name = "PolisJAPAN-Contact"
  role          = "arn:aws:iam::133078632695:role/service-role/PolisJAPAN-Contact-role-v6p45kri"
  runtime       = "python3.14"
  handler       = "lambda_function.lambda_handler"
  memory_size   = 128
  timeout       = 3
  architectures = ["x86_64"]

  # 実コードはTerraform管理外（ignore_changes）。filenameはスキーマ必須のためのプレースホルダで、
  # ignore_changesにより実際にアップロードされることはない
  filename = "${path.module}/lambda-placeholder.zip"

  lifecycle {
    # コードはコンソールからデプロイ済みのものを維持（Terraformはインフラ属性のみ管理）
    ignore_changes = [filename, s3_bucket, s3_key, source_code_hash, publish, layers]
  }
}

resource "aws_lambda_function" "share_ogp" {
  provider      = aws.us_east_1
  function_name = "PolisJAPAN-GetOGP"
  role          = "arn:aws:iam::133078632695:role/service-role/PolisJAPAN-GetOGP-role-b6paet6d"
  runtime       = "python3.13"
  handler       = "lambda_function.lambda_handler"
  memory_size   = 128
  timeout       = 3
  architectures = ["x86_64"]

  filename = "${path.module}/lambda-placeholder.zip"

  lifecycle {
    ignore_changes = [filename, s3_bucket, s3_key, source_code_hash, publish, layers]
  }
}

resource "aws_cloudwatch_log_group" "contact" {
  provider          = aws.us_east_1
  name              = "/aws/lambda/PolisJAPAN-Contact"
  retention_in_days = 0
}

resource "aws_cloudwatch_log_group" "share_ogp" {
  provider          = aws.us_east_1
  name              = "/aws/lambda/PolisJAPAN-GetOGP"
  retention_in_days = 0
}

# ---- API Gateway（本体とステージのみ・メソッド定義は管理外） ----

resource "aws_api_gateway_rest_api" "contact" {
  provider = aws.us_east_1
  name     = "PolisJAPAN-Contact"

  endpoint_configuration {
    types = ["REGIONAL"]
  }
}

resource "aws_api_gateway_rest_api" "share" {
  provider = aws.us_east_1
  name     = "PolisJAPAN-GetOGP"

  endpoint_configuration {
    types = ["REGIONAL"]
  }
}

resource "aws_api_gateway_stage" "contact" {
  provider      = aws.us_east_1
  rest_api_id   = aws_api_gateway_rest_api.contact.id
  stage_name    = "production"
  deployment_id = "8w6pj8"
}

resource "aws_api_gateway_stage" "share" {
  provider      = aws.us_east_1
  rest_api_id   = aws_api_gateway_rest_api.share.id
  stage_name    = "Production"
  deployment_id = "2dk3ch"
}
