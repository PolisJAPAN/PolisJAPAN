# ============================================================
# 既存の静的サイトS3バケット（手動作成）のTerraform取り込み
# LP: pol-is.jp / アプリ: app.pol-is.jp（csv/含む＝データ本体）
# どちらもS3ウェブサイトエンドポイント + 公開読み取りポリシー構成
# ============================================================

import {
  to = aws_s3_bucket.lp
  id = "pol-is.jp"
}

import {
  to = aws_s3_bucket_website_configuration.lp
  id = "pol-is.jp"
}

import {
  to = aws_s3_bucket_policy.lp
  id = "pol-is.jp"
}

import {
  to = aws_s3_bucket_public_access_block.lp
  id = "pol-is.jp"
}

import {
  to = aws_s3_bucket.app
  id = "app.pol-is.jp"
}

import {
  to = aws_s3_bucket_website_configuration.app
  id = "app.pol-is.jp"
}

import {
  to = aws_s3_bucket_policy.app
  id = "app.pol-is.jp"
}

import {
  to = aws_s3_bucket_public_access_block.app
  id = "app.pol-is.jp"
}

import {
  to = aws_s3_bucket_versioning.app
  id = "app.pol-is.jp"
}

import {
  to = aws_s3_bucket_lifecycle_configuration.app
  id = "app.pol-is.jp"
}

# ---- LP: pol-is.jp ----

resource "aws_s3_bucket" "lp" {
  bucket = "pol-is.jp"

  lifecycle {
    # LPサイトの実体。誤destroyを拒否（非空バケットはAWS側でも削除拒否される）
    prevent_destroy = true
  }
}

resource "aws_s3_bucket_website_configuration" "lp" {
  bucket = aws_s3_bucket.lp.id

  index_document {
    suffix = "index.html"
  }
}

resource "aws_s3_bucket_public_access_block" "lp" {
  bucket                  = aws_s3_bucket.lp.id
  block_public_acls       = false
  block_public_policy     = false
  ignore_public_acls      = false
  restrict_public_buckets = false
}

resource "aws_s3_bucket_policy" "lp" {
  bucket = aws_s3_bucket.lp.id

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Sid       = "PublicReadGetObject"
      Effect    = "Allow"
      Principal = "*"
      Action    = "s3:GetObject"
      Resource  = "arn:aws:s3:::pol-is.jp/*"
    }]
  })
}

# ---- アプリ: app.pol-is.jp（テーマ/レポートCSVのデータ本体を含む） ----

resource "aws_s3_bucket" "app" {
  bucket = "app.pol-is.jp"

  lifecycle {
    # アプリ静的ファイル + csv/（テーマ・レポートのデータ本体）。誤destroyを拒否
    prevent_destroy = true
  }
}

resource "aws_s3_bucket_website_configuration" "app" {
  bucket = aws_s3_bucket.app.id

  index_document {
    suffix = "index.html"
  }
}

resource "aws_s3_bucket_public_access_block" "app" {
  bucket                  = aws_s3_bucket.app.id
  block_public_acls       = false
  block_public_policy     = false
  ignore_public_acls      = false
  restrict_public_buckets = false
}

resource "aws_s3_bucket_policy" "app" {
  bucket = aws_s3_bucket.app.id

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Sid       = "PublicReadGetObject"
      Effect    = "Allow"
      Principal = "*"
      Action    = "s3:GetObject"
      Resource  = "arn:aws:s3:::app.pol-is.jp/*"
    }]
  })
}

resource "aws_s3_bucket_versioning" "app" {
  bucket = aws_s3_bucket.app.id

  versioning_configuration {
    status = "Enabled"
  }
}

resource "aws_s3_bucket_lifecycle_configuration" "app" {
  bucket                                 = aws_s3_bucket.app.id
  transition_default_minimum_object_size = "all_storage_classes_128K"

  rule {
    id     = "BackUp 1-Week"
    status = "Enabled"

    noncurrent_version_expiration {
      noncurrent_days = 7
    }
  }
}
