output "url" {
  value = "https://${var.admin_domain}/"
}

output "bucket" {
  description = "管理画面の静的ファイルをsyncする先"
  value       = aws_s3_bucket.admin.bucket
}

output "distribution_id" {
  value = aws_cloudfront_distribution.admin.id
}
