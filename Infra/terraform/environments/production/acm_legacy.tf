# ============================================================
# 既存ACM証明書（us-east-1・CloudFront用）のTerraform取り込み
# admin.pol-is.jp / api.pol-is.jp 用は admin-site / api モジュールで管理済み
# ============================================================

import {
  to = aws_acm_certificate.lp
  id = "arn:aws:acm:us-east-1:133078632695:certificate/73a097a7-00ae-420a-a34b-6cb12325781e"
}

import {
  to = aws_acm_certificate.app
  id = "arn:aws:acm:us-east-1:133078632695:certificate/d2de909d-32f8-44c8-a8e1-c1125dbe5ce4"
}

import {
  to = aws_acm_certificate.share
  id = "arn:aws:acm:us-east-1:133078632695:certificate/ebac6943-51b8-4190-a418-13ed4ffdf772"
}

import {
  to = aws_acm_certificate.contact
  id = "arn:aws:acm:us-east-1:133078632695:certificate/fc5c7f75-719f-4264-8690-461c412cd7ee"
}

resource "aws_acm_certificate" "lp" {
  provider          = aws.us_east_1
  domain_name       = "pol-is.jp"
  validation_method = "DNS"

  lifecycle {
    # CloudFrontが参照中の証明書を先に消さない
    create_before_destroy = true
  }
}

resource "aws_acm_certificate" "app" {
  provider          = aws.us_east_1
  domain_name       = "app.pol-is.jp"
  validation_method = "DNS"

  lifecycle {
    create_before_destroy = true
  }
}

resource "aws_acm_certificate" "share" {
  provider          = aws.us_east_1
  domain_name       = "share.pol-is.jp"
  validation_method = "DNS"

  lifecycle {
    create_before_destroy = true
  }
}

resource "aws_acm_certificate" "contact" {
  provider          = aws.us_east_1
  domain_name       = "contact.pol-is.jp"
  validation_method = "DNS"

  lifecycle {
    create_before_destroy = true
  }
}
