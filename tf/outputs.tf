output "fastapi_url" {
  description = "Public URL for the FastAPI Lambda function."
  value       = aws_lambda_function_url.fastapi.function_url
}

output "jobs_table_arn" {
  description = "DynamoDB jobs table ARN."
  value       = aws_dynamodb_table.jobs.arn
}

output "jobs_table_name" {
  description = "Set this value as DYNAMODB_JOBS_TABLE for the backend Lambda."
  value       = aws_dynamodb_table.jobs.name
}
