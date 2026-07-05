variable "aws_profile" {
  description = "使用するAWS CLIプロファイル名（terraform-deployユーザー）"
  type        = string
  default     = "terraform"
}

variable "root_domain" {
  description = "Route53で管理しているルートドメイン"
  type        = string
  default     = "pol-is.jp"
}

variable "api_domain" {
  description = "APIのカスタムドメイン（カットオーバー時にRoute53を手動で切り替える）"
  type        = string
  default     = "api.pol-is.jp"
}

variable "admin_domain" {
  description = "管理画面の配信ドメイン（新設サブドメイン）"
  type        = string
  default     = "admin.pol-is.jp"
}

variable "app_bucket" {
  description = "テーマ/レポートCSVを保持する既存のS3バケット名（Terraform管理外・アクセス権のみ付与）"
  type        = string
  default     = "app.pol-is.jp"
}

variable "client_base_url" {
  description = "WEBアプリのベースURL（Lambda環境変数用）"
  type        = string
  default     = "https://app.pol-is.jp/"
}

variable "cors_allow_origins" {
  description = "APIのCORS許可オリジン（カンマ区切りでLambda環境変数に渡す）"
  type        = list(string)
  default     = ["https://app.pol-is.jp", "https://pol-is.jp", "https://admin.pol-is.jp"]
}

variable "admin_allow_ips" {
  description = "管理画面・admin APIを許可するIP(CIDR)リスト"
  type        = list(string)
}

variable "alert_email" {
  description = "アラート通知先メールアドレス（SNS購読。apply後に確認メールの承認が必要）"
  type        = string
}

variable "api_image_uri" {
  description = "Lambda api / batch-update 用コンテナイメージURI（ECRへのpush後に指定）。空文字ならLambda系リソースを作成しない"
  type        = string
  default     = ""
}

variable "batch_create_image_uri" {
  description = "Lambda batch-create 用（Chromium同梱）コンテナイメージURI。空文字なら作成しない"
  type        = string
  default     = ""
}

variable "scheduler_state" {
  description = "EventBridge Schedulerの状態。カットオーバーまでDISABLEDを維持し、二重実行（旧cronとの併走によるpol.is二重投稿）を防ぐ"
  type        = string
  default     = "DISABLED"

  validation {
    condition     = contains(["ENABLED", "DISABLED"], var.scheduler_state)
    error_message = "scheduler_state は ENABLED か DISABLED を指定してください。"
  }
}

variable "enable_health_check" {
  description = "Route53ヘルスチェックとアラームを作成するか（現行EC2に対しても有効に機能する）"
  type        = bool
  default     = true
}
