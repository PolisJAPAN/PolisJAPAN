output "function_names" {
  value = [for f in aws_lambda_function.batch : f.function_name]
}
