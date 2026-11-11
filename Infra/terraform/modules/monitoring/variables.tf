variable "api_domain" {
  type = string
}

variable "alert_email" {
  type = string
}

variable "enable_health_check" {
  type    = bool
  default = true
}

variable "lambda_function_names" {
  description = "エラーアラームを設定するLambda関数名のリスト"
  type        = list(string)
  default     = []
}

variable "enable_publish_backlog_alarms" {
  description = "投稿バッチ(batch-create)の滞留アラームを作成するか"
  type        = bool
  default     = false
}
