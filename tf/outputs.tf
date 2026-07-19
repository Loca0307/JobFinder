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

output "github_actions_deploy_role_arn" {
  description = "Set this ARN as the GitHub repository variable AWS_DEPLOY_ROLE_ARN."
  value       = aws_iam_role.github_actions_lambda_deploy.arn
}

output "github_actions_frontend_deploy_role_arn" {
  description = "Set this ARN as the GitHub repository variable AWS_FRONTEND_DEPLOY_ROLE_ARN."
  value       = aws_iam_role.github_actions_frontend_deploy.arn
}
