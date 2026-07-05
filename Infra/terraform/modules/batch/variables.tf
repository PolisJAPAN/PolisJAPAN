variable "update_image_uri" {
  description = "batch-update用イメージ（apiと同一イメージを使用）"
  type        = string
}

variable "create_image_uri" {
  description = "batch-create用イメージ（Chromium同梱）"
  type        = string
}

variable "app_bucket" {
  type = string
}

variable "extra_bucket_arns" {
  description = "追加でアクセスを許可するバケットARN（E2Eサンドボックス用）"
  type        = list(string)
  default     = []
}

variable "drafts_table_arn" {
  type = string
}

variable "ssm_parameter_arns" {
  type = list(string)
}

variable "scheduler_state" {
  type = string
}

variable "environment_variables" {
  type      = map(string)
  sensitive = true
}
