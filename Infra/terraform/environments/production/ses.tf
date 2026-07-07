# ============================================================
# 既存SES（us-east-1・送信ドメイン認証）のTerraform取り込み
# メールアドレスIDは個人アドレスのため管理外（コードに残さない）
# ============================================================

import {
  to = aws_ses_domain_identity.main
  id = "pol-is.jp"
}

import {
  to = aws_ses_domain_dkim.main
  id = "pol-is.jp"
}

import {
  to = aws_ses_domain_mail_from.main
  id = "pol-is.jp"
}

resource "aws_ses_domain_identity" "main" {
  provider = aws.us_east_1
  domain   = "pol-is.jp"
}

resource "aws_ses_domain_dkim" "main" {
  provider = aws.us_east_1
  domain   = aws_ses_domain_identity.main.domain
}

resource "aws_ses_domain_mail_from" "main" {
  provider         = aws.us_east_1
  domain           = aws_ses_domain_identity.main.domain
  mail_from_domain = "mail.pol-is.jp"
}
