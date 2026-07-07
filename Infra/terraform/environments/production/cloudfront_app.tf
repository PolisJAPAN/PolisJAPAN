# ============================================================
# 既存の app.pol-is.jp CloudFront（手動作成・E1VDGUET2Z2OBX）を
# Terraform管理下に取り込む。既存設定を完全再現した上で import する。
# 目的: /csv/* にクエリ(_v)込みキャッシュのビヘイビアを安全に追加するため。
# （Phase 5「既存リソースのTerraform取り込み」の app CloudFront 分の前倒し）
# ============================================================

import {
  to = aws_cloudfront_distribution.app
  id = "E1VDGUET2Z2OBX"
}

# CSV配信用カスタムキャッシュポリシー: クエリ "_v"(5分バケット)のみキャッシュキーに含める。
# クライアント(common.js)が付ける ?_v=<5分バケット> ごとに別キャッシュとなり、
# 5分ごとに全エッジ共通で確実に切り替わる（TTLのエッジばらつきに依存しない）。
resource "aws_cloudfront_cache_policy" "csv_versioned" {
  name        = "polisjapan-csv-versioned"
  comment     = "CSV: cache by _v query bucket (5min), origin fetch once per bucket"
  min_ttl     = 0
  default_ttl = 300
  max_ttl     = 300

  parameters_in_cache_key_and_forwarded_to_origin {
    enable_accept_encoding_gzip   = true
    enable_accept_encoding_brotli = true

    query_strings_config {
      query_string_behavior = "whitelist"
      query_strings {
        items = ["_v"]
      }
    }
    cookies_config {
      cookie_behavior = "none"
    }
    headers_config {
      header_behavior = "none"
    }
  }
}

resource "aws_cloudfront_distribution" "app" {
  enabled         = true
  is_ipv6_enabled = true
  http_version    = "http2"
  price_class     = "PriceClass_All"
  aliases         = ["app.pol-is.jp"]

  origin {
    domain_name = "app.pol-is.jp.s3-website.ap-northeast-3.amazonaws.com"
    origin_id   = "app.pol-is.jp.s3-website.ap-northeast-3.amazonaws.com"

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
    target_origin_id       = "app.pol-is.jp.s3-website.ap-northeast-3.amazonaws.com"
    viewer_protocol_policy = "redirect-to-https"
    allowed_methods        = ["GET", "HEAD"]
    cached_methods         = ["GET", "HEAD"]
    compress               = true
    cache_policy_id        = "658327ea-f89d-4fab-a63d-7e88639e58f6" # Managed-CachingOptimized
  }

  # 追加: CSV配信のみ、クエリ(_v)込みでキャッシュする。他パスは default_cache_behavior のまま。
  ordered_cache_behavior {
    path_pattern           = "/csv/*"
    target_origin_id       = "app.pol-is.jp.s3-website.ap-northeast-3.amazonaws.com"
    viewer_protocol_policy = "redirect-to-https"
    allowed_methods        = ["GET", "HEAD"]
    cached_methods         = ["GET", "HEAD"]
    compress               = true
    cache_policy_id        = aws_cloudfront_cache_policy.csv_versioned.id
  }

  # 既存のNameタグを保持（provider default_tags で Project/ManagedBy も付与される）
  tags = {
    Name = "app.pol-is.jp"
  }

  restrictions {
    geo_restriction {
      restriction_type = "none"
    }
  }

  viewer_certificate {
    acm_certificate_arn      = "arn:aws:acm:us-east-1:133078632695:certificate/d2de909d-32f8-44c8-a8e1-c1125dbe5ce4"
    ssl_support_method       = "sni-only"
    minimum_protocol_version = "TLSv1.2_2021"
  }
}
