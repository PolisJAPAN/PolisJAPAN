# ============================================================
# 既存CloudFront（LP / share / contact）のTerraform取り込み
# app.pol-is.jp は cloudfront_app.tf で取り込み済み
# ============================================================

import {
  to = aws_cloudfront_distribution.lp
  id = "E1L9GH70CTWAY6"
}

import {
  to = aws_cloudfront_distribution.share
  id = "E2VD4O5M17XG0X"
}

import {
  to = aws_cloudfront_distribution.contact
  id = "E2X1TX47YAAO8F"
}

# ---- LP: pol-is.jp（S3ウェブサイトオリジン・appと同型） ----

resource "aws_cloudfront_distribution" "lp" {
  enabled         = true
  is_ipv6_enabled = true
  http_version    = "http2"
  price_class     = "PriceClass_All"
  aliases         = ["pol-is.jp"]

  origin {
    domain_name = "pol-is.jp.s3-website.ap-northeast-3.amazonaws.com"
    origin_id   = "pol-is.jp.s3.ap-northeast-3.amazonaws.com-mg7ti9qt23g"

    custom_origin_config {
      http_port                = 80
      https_port               = 443
      origin_protocol_policy   = "http-only"
      origin_ssl_protocols     = ["SSLv3", "TLSv1", "TLSv1.1", "TLSv1.2"]
      origin_read_timeout      = 30
      origin_keepalive_timeout = 5
    }
  }

  default_cache_behavior {
    target_origin_id       = "pol-is.jp.s3.ap-northeast-3.amazonaws.com-mg7ti9qt23g"
    viewer_protocol_policy = "redirect-to-https"
    allowed_methods        = ["GET", "HEAD"]
    cached_methods         = ["GET", "HEAD"]
    compress               = true
    cache_policy_id        = "658327ea-f89d-4fab-a63d-7e88639e58f6" # Managed-CachingOptimized
  }

  tags = {
    Name = "polis-japan"
  }

  restrictions {
    geo_restriction {
      restriction_type = "none"
    }
  }

  viewer_certificate {
    acm_certificate_arn      = aws_acm_certificate.lp.arn
    ssl_support_method       = "sni-only"
    minimum_protocol_version = "TLSv1.2_2021"
  }
}

# ---- share.pol-is.jp（API GWオリジン・キャッシュ無効） ----

resource "aws_cloudfront_distribution" "share" {
  enabled         = true
  is_ipv6_enabled = true
  http_version    = "http2"
  price_class     = "PriceClass_All"
  aliases         = ["share.pol-is.jp"]

  origin {
    domain_name = "jh9u2wjvea.execute-api.us-east-1.amazonaws.com"
    origin_id   = "jh9u2wjvea.execute-api.us-east-1.amazonaws.com-mhuf56w8ii7"
    origin_path = "/Production"

    custom_origin_config {
      http_port                = 80
      https_port               = 443
      origin_protocol_policy   = "https-only"
      origin_ssl_protocols     = ["TLSv1.2"]
      origin_read_timeout      = 30
      origin_keepalive_timeout = 5
    }
  }

  default_cache_behavior {
    target_origin_id         = "jh9u2wjvea.execute-api.us-east-1.amazonaws.com-mhuf56w8ii7"
    viewer_protocol_policy   = "redirect-to-https"
    allowed_methods          = ["GET", "HEAD", "OPTIONS", "PUT", "POST", "PATCH", "DELETE"]
    cached_methods           = ["GET", "HEAD"]
    compress                 = true
    cache_policy_id          = "4135ea2d-6df8-44a3-9df3-4b5a84be39ad" # Managed-CachingDisabled
    origin_request_policy_id = "b689b0a8-53d0-40ab-baf2-68738e2966ac" # Managed-AllViewerExceptHostHeader
  }

  tags = {
    Name = "share.pol-is.jp"
  }

  restrictions {
    geo_restriction {
      restriction_type = "none"
    }
  }

  viewer_certificate {
    acm_certificate_arn      = aws_acm_certificate.share.arn
    ssl_support_method       = "sni-only"
    minimum_protocol_version = "TLSv1.2_2021"
  }
}

# ---- contact.pol-is.jp（API GWオリジン・キャッシュ無効） ----

resource "aws_cloudfront_distribution" "contact" {
  enabled         = true
  is_ipv6_enabled = true
  http_version    = "http2"
  price_class     = "PriceClass_All"
  aliases         = ["contact.pol-is.jp"]

  origin {
    domain_name = "7r1e9gjfmk.execute-api.us-east-1.amazonaws.com"
    origin_id   = "7r1e9gjfmk.execute-api.us-east-1.amazonaws.com-mhyb6ihef43"
    origin_path = "/production"

    custom_origin_config {
      http_port                = 80
      https_port               = 443
      origin_protocol_policy   = "https-only"
      origin_ssl_protocols     = ["TLSv1.2"]
      origin_read_timeout      = 30
      origin_keepalive_timeout = 5
    }
  }

  default_cache_behavior {
    target_origin_id         = "7r1e9gjfmk.execute-api.us-east-1.amazonaws.com-mhyb6ihef43"
    viewer_protocol_policy   = "redirect-to-https"
    allowed_methods          = ["GET", "HEAD", "OPTIONS", "PUT", "POST", "PATCH", "DELETE"]
    cached_methods           = ["GET", "HEAD"]
    compress                 = true
    cache_policy_id          = "4135ea2d-6df8-44a3-9df3-4b5a84be39ad" # Managed-CachingDisabled
    origin_request_policy_id = "b689b0a8-53d0-40ab-baf2-68738e2966ac" # Managed-AllViewerExceptHostHeader
  }

  tags = {
    Name = "contact.pol-is.jp"
  }

  restrictions {
    geo_restriction {
      restriction_type = "none"
    }
  }

  viewer_certificate {
    acm_certificate_arn      = aws_acm_certificate.contact.arn
    ssl_support_method       = "sni-only"
    minimum_protocol_version = "TLSv1.2_2021"
  }
}
