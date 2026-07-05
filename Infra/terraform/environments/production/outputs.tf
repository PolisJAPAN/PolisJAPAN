output "drafts_table_name" {
  description = "DynamoDBテーブル名"
  value       = module.data.drafts_table_name
}

output "ecr_api_repository_url" {
  description = "api/batch-update用イメージのpush先ECR"
  value       = module.data.ecr_api_repository_url
}

output "ecr_batch_create_repository_url" {
  description = "batch-create(Chromium)用イメージのpush先ECR"
  value       = module.data.ecr_batch_create_repository_url
}

output "api_gateway_default_endpoint" {
  description = "API GWのデフォルトエンドポイント（カットオーバー前のE2Eテストに使用）"
  value       = length(module.api) > 0 ? module.api[0].default_endpoint : null
}

output "api_custom_domain_target" {
  description = "カットオーバー時にRoute53のapi.pol-is.jpをこのエイリアス先に向ける"
  value       = length(module.api) > 0 ? module.api[0].custom_domain_target : null
}

output "admin_site_url" {
  description = "管理画面URL"
  value       = module.admin_site.url
}

output "archive_bucket" {
  description = "MySQLダンプ等の保全先バケット"
  value       = module.data.archive_bucket
}
