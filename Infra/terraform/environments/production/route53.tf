# ============================================================
# Route53 ホストゾーン pol-is.jp と既存レコードのTerraform取り込み
# admin.pol-is.jp のAレコードとACM検証CNAME(api/admin)はモジュール側で管理済み
# NS/SOA はゾーンリソースが暗黙管理するため個別importしない
# ============================================================

import {
  to = aws_route53_zone.main
  id = "Z0840308B50FRGAA6C2H"
}

resource "aws_route53_zone" "main" {
  name    = "pol-is.jp"
  comment = ""

  lifecycle {
    # ドメインのDNS本体。誤destroyを拒否する
    prevent_destroy = true
  }
}

import {
  to = aws_route53_record.root_a
  id = "Z0840308B50FRGAA6C2H_pol-is.jp_A"
}

resource "aws_route53_record" "root_a" {
  zone_id = aws_route53_zone.main.zone_id
  name    = "pol-is.jp"
  type    = "A"

  alias {
    name                   = aws_cloudfront_distribution.lp.domain_name
    zone_id                = aws_cloudfront_distribution.lp.hosted_zone_id
    evaluate_target_health = false
  }
}

import {
  to = aws_route53_record.app_a
  id = "Z0840308B50FRGAA6C2H_app.pol-is.jp_A"
}

resource "aws_route53_record" "app_a" {
  zone_id = aws_route53_zone.main.zone_id
  name    = "app.pol-is.jp"
  type    = "A"

  alias {
    name                   = aws_cloudfront_distribution.app.domain_name
    zone_id                = aws_cloudfront_distribution.app.hosted_zone_id
    evaluate_target_health = false
  }
}

import {
  to = aws_route53_record.share_a
  id = "Z0840308B50FRGAA6C2H_share.pol-is.jp_A"
}

resource "aws_route53_record" "share_a" {
  zone_id = aws_route53_zone.main.zone_id
  name    = "share.pol-is.jp"
  type    = "A"

  alias {
    name                   = aws_cloudfront_distribution.share.domain_name
    zone_id                = aws_cloudfront_distribution.share.hosted_zone_id
    evaluate_target_health = false
  }
}

import {
  to = aws_route53_record.contact_a
  id = "Z0840308B50FRGAA6C2H_contact.pol-is.jp_A"
}

resource "aws_route53_record" "contact_a" {
  zone_id = aws_route53_zone.main.zone_id
  name    = "contact.pol-is.jp"
  type    = "A"

  alias {
    name                   = aws_cloudfront_distribution.contact.domain_name
    zone_id                = aws_cloudfront_distribution.contact.hosted_zone_id
    evaluate_target_health = false
  }
}

import {
  to = aws_route53_record.api_a
  id = "Z0840308B50FRGAA6C2H_api.pol-is.jp_A"
}

resource "aws_route53_record" "api_a" {
  zone_id = aws_route53_zone.main.zone_id
  name    = "api.pol-is.jp"
  type    = "A"

  alias {
    name                   = module.api[0].custom_domain_target.domain_name
    zone_id                = module.api[0].custom_domain_target.hosted_zone_id
    evaluate_target_health = false
  }
}

import {
  to = aws_route53_record.dkim_1
  id = "Z0840308B50FRGAA6C2H_26zikil5h4riipotmvbvk4na75lpaqax._domainkey.pol-is.jp_CNAME"
}

resource "aws_route53_record" "dkim_1" {
  zone_id = aws_route53_zone.main.zone_id
  name    = "26zikil5h4riipotmvbvk4na75lpaqax._domainkey.pol-is.jp"
  type    = "CNAME"
  ttl     = 1800
  records = ["26zikil5h4riipotmvbvk4na75lpaqax.dkim.amazonses.com"]
}

import {
  to = aws_route53_record.dkim_2
  id = "Z0840308B50FRGAA6C2H_phzorkxkxcpdp4sqhi357t3qpx23zc43._domainkey.pol-is.jp_CNAME"
}

resource "aws_route53_record" "dkim_2" {
  zone_id = aws_route53_zone.main.zone_id
  name    = "phzorkxkxcpdp4sqhi357t3qpx23zc43._domainkey.pol-is.jp"
  type    = "CNAME"
  ttl     = 1800
  records = ["phzorkxkxcpdp4sqhi357t3qpx23zc43.dkim.amazonses.com"]
}

import {
  to = aws_route53_record.dkim_3
  id = "Z0840308B50FRGAA6C2H_zfnbgmslsselsm2e7dppplekjzuxxxit._domainkey.pol-is.jp_CNAME"
}

resource "aws_route53_record" "dkim_3" {
  zone_id = aws_route53_zone.main.zone_id
  name    = "zfnbgmslsselsm2e7dppplekjzuxxxit._domainkey.pol-is.jp"
  type    = "CNAME"
  ttl     = 1800
  records = ["zfnbgmslsselsm2e7dppplekjzuxxxit.dkim.amazonses.com"]
}

import {
  to = aws_route53_record.cert_validation_root
  id = "Z0840308B50FRGAA6C2H__fca07271a613ccdf7eee1f5019dd6e9d.pol-is.jp_CNAME"
}

resource "aws_route53_record" "cert_validation_root" {
  zone_id = aws_route53_zone.main.zone_id
  name    = "_fca07271a613ccdf7eee1f5019dd6e9d.pol-is.jp"
  type    = "CNAME"
  ttl     = 300
  records = ["_4d024037c54f3985b98b88185ee3b405.xlfgrmvvlj.acm-validations.aws."]
}

import {
  to = aws_route53_record.cert_validation_app
  id = "Z0840308B50FRGAA6C2H__c6b77cd4bc92bd12e6c174c516dd3106.app.pol-is.jp_CNAME"
}

resource "aws_route53_record" "cert_validation_app" {
  zone_id = aws_route53_zone.main.zone_id
  name    = "_c6b77cd4bc92bd12e6c174c516dd3106.app.pol-is.jp"
  type    = "CNAME"
  ttl     = 300
  records = ["_ca4cb15621b767121a5e5c4ce9174f2d.xlfgrmvvlj.acm-validations.aws."]
}

import {
  to = aws_route53_record.cert_validation_share
  id = "Z0840308B50FRGAA6C2H__62d8a657a46518ae153fad64da958bb0.share.pol-is.jp_CNAME"
}

resource "aws_route53_record" "cert_validation_share" {
  zone_id = aws_route53_zone.main.zone_id
  name    = "_62d8a657a46518ae153fad64da958bb0.share.pol-is.jp"
  type    = "CNAME"
  ttl     = 300
  records = ["_8c1d0d4ab28cc788e99b0e45bf8a6214.jkddzztszm.acm-validations.aws."]
}

import {
  to = aws_route53_record.cert_validation_contact
  id = "Z0840308B50FRGAA6C2H__d90a87e4a755145efb515416cf7b830c.contact.pol-is.jp_CNAME"
}

resource "aws_route53_record" "cert_validation_contact" {
  zone_id = aws_route53_zone.main.zone_id
  name    = "_d90a87e4a755145efb515416cf7b830c.contact.pol-is.jp"
  type    = "CNAME"
  ttl     = 300
  records = ["_08b71bd93f66d103f40455a58593a0ee.jkddzztszm.acm-validations.aws."]
}

import {
  to = aws_route53_record.ses_mx
  id = "Z0840308B50FRGAA6C2H_mail.pol-is.jp_MX"
}

resource "aws_route53_record" "ses_mx" {
  zone_id = aws_route53_zone.main.zone_id
  name    = "mail.pol-is.jp"
  type    = "MX"
  ttl     = 300
  records = ["10 feedback-smtp.us-east-1.amazonses.com"]
}

import {
  to = aws_route53_record.ses_spf
  id = "Z0840308B50FRGAA6C2H_mail.pol-is.jp_TXT"
}

resource "aws_route53_record" "ses_spf" {
  zone_id = aws_route53_zone.main.zone_id
  name    = "mail.pol-is.jp"
  type    = "TXT"
  ttl     = 300
  records = ["v=spf1 include:amazonses.com ~all"]
}
