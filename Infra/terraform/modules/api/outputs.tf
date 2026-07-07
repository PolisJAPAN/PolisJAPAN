output "function_name" {
  value = aws_lambda_function.api.function_name
}

output "default_endpoint" {
  description = "カットオーバー前のE2Eテストに使うデフォルトエンドポイント"
  value       = aws_apigatewayv2_api.api.api_endpoint
}

output "custom_domain_target" {
  description = "Route53切替時のエイリアス先（regional domain name）"
  value = {
    domain_name    = aws_apigatewayv2_domain_name.api.domain_name_configuration[0].target_domain_name
    hosted_zone_id = aws_apigatewayv2_domain_name.api.domain_name_configuration[0].hosted_zone_id
  }
}
