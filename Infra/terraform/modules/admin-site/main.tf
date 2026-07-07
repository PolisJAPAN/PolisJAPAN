# ============================================================
# 管理画面: S3(非公開+OAC) + CloudFront + CloudFront Function(IP制限)
# 現行の api.pol-is.jp/dashboard/ (EC2 nginx) を置き換える
# admin.pol-is.jp は新設サブドメインのため、Route53への追加は安全
# ============================================================

terraform {
  required_providers {
    aws = {
      source                = "hashicorp/aws"
      configuration_aliases = [aws.us_east_1]
    }
  }
}

# ---- S3（非公開・CloudFront OAC経由のみ） ----

resource "aws_s3_bucket" "admin" {
  bucket = var.admin_domain
}

resource "aws_s3_bucket_public_access_block" "admin" {
  bucket                  = aws_s3_bucket.admin.id
  block_public_acls       = true
  block_public_policy     = true
  ignore_public_acls      = true
  restrict_public_buckets = true
}

resource "aws_s3_bucket_policy" "admin" {
  bucket = aws_s3_bucket.admin.id

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Sid       = "AllowCloudFrontOAC"
      Effect    = "Allow"
      Principal = { Service = "cloudfront.amazonaws.com" }
      Action    = "s3:GetObject"
      Resource  = "${aws_s3_bucket.admin.arn}/*"
      Condition = {
        StringEquals = { "AWS:SourceArn" = aws_cloudfront_distribution.admin.arn }
      }
    }]
  })

  depends_on = [aws_s3_bucket_public_access_block.admin]
}

# ---- ACM（CloudFront用: us-east-1） ----

resource "aws_acm_certificate" "admin" {
  provider          = aws.us_east_1
  domain_name       = var.admin_domain
  validation_method = "DNS"

  lifecycle {
    create_before_destroy = true
  }
}

resource "aws_route53_record" "admin_cert_validation" {
  for_each = {
    for dvo in aws_acm_certificate.admin.domain_validation_options : dvo.domain_name => {
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

resource "aws_acm_certificate_validation" "admin" {
  provider                = aws.us_east_1
  certificate_arn         = aws_acm_certificate.admin.arn
  validation_record_fqdns = [for r in aws_route53_record.admin_cert_validation : r.fqdn]
}

# ---- CloudFront Function: IP許可リスト検査 ----
# WAF($5/月〜)を使わずにIP制限を実現する。CloudFront Functionは実質無料

resource "aws_cloudfront_function" "ip_check" {
  name    = "polisjapan-admin-ip-check"
  runtime = "cloudfront-js-2.0"
  publish = true
  code = templatefile("${path.module}/ip_check.js.tftpl", {
    allow_ips_json = jsonencode(var.admin_allow_ips)
  })
}

# ---- CloudFront ----

resource "aws_cloudfront_origin_access_control" "admin" {
  name                              = "polisjapan-admin-oac"
  origin_access_control_origin_type = "s3"
  signing_behavior                  = "always"
  signing_protocol                  = "sigv4"
}

resource "aws_cloudfront_distribution" "admin" {
  enabled             = true
  comment             = "PolisJAPAN admin dashboard"
  aliases             = [var.admin_domain]
  default_root_object = "index.html"
  price_class         = "PriceClass_200"

  origin {
    domain_name              = aws_s3_bucket.admin.bucket_regional_domain_name
    origin_id                = "s3-admin"
    origin_access_control_id = aws_cloudfront_origin_access_control.admin.id
  }

  default_cache_behavior {
    target_origin_id       = "s3-admin"
    viewer_protocol_policy = "redirect-to-https"
    allowed_methods        = ["GET", "HEAD"]
    cached_methods         = ["GET", "HEAD"]
    compress               = true
    # AWS managed CachingOptimized
    cache_policy_id = "658327ea-f89d-4fab-a63d-7e88639e58f6"

    function_association {
      event_type   = "viewer-request"
      function_arn = aws_cloudfront_function.ip_check.arn
    }
  }

  restrictions {
    geo_restriction {
      restriction_type = "none"
    }
  }

  viewer_certificate {
    acm_certificate_arn      = aws_acm_certificate_validation.admin.certificate_arn
    ssl_support_method       = "sni-only"
    minimum_protocol_version = "TLSv1.2_2021"
  }
}

# ---- Route53（新設サブドメインの追加のみ・既存レコードには触れない） ----

resource "aws_route53_record" "admin" {
  zone_id = var.zone_id
  name    = var.admin_domain
  type    = "A"

  alias {
    name                   = aws_cloudfront_distribution.admin.domain_name
    zone_id                = aws_cloudfront_distribution.admin.hosted_zone_id
    evaluate_target_health = false
  }
}
