variable "api_domain" {
  type = string
}

variable "zone_id" {
  description = "ACM検証レコードを追加するRoute53ゾーンID"
  type        = string
}

variable "image_uri" {
  description = "LambdaコンテナイメージURI"
  type        = string
}

variable "app_bucket" {
  description = "CSVを保持する既存S3バケット名"
  type        = string
}

variable "extra_bucket_arns" {
  description = "追加でアクセスを許可するバケットARN（E2Eサンドボックス用）"
  type        = list(string)
  default     = []
}

variable "drafts_table_name" {
  type = string
}

variable "drafts_table_arn" {
  type = string
}

variable "ssm_parameter_arns" {
  type = list(string)
}

variable "environment_variables" {
  type      = map(string)
  sensitive = true
}
