output "drafts_table_name" {
  value = aws_dynamodb_table.drafts.name
}

output "drafts_table_arn" {
  value = aws_dynamodb_table.drafts.arn
}

output "archive_bucket" {
  value = aws_s3_bucket.archive.bucket
}

output "ecr_api_repository_url" {
  value = aws_ecr_repository.api.repository_url
}

output "ecr_batch_create_repository_url" {
  value = aws_ecr_repository.batch_create.repository_url
}

output "ssm_parameter_names" {
  value = { for k, p in aws_ssm_parameter.secrets : k => p.name }
}

output "ssm_parameter_arns" {
  value = [for p in aws_ssm_parameter.secrets : p.arn]
}
