variable "admin_domain" {
  type = string
}

variable "zone_id" {
  type = string
}

variable "admin_allow_ips" {
  description = "許可するIP(CIDR)リスト"
  type        = list(string)
}
