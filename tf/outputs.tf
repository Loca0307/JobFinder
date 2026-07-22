output "fastapi_url" {
  description = "IAM-protected FastAPI Lambda Function URL used as the CloudFront API origin."
  value       = aws_lambda_function_url.fastapi.function_url
}

output "private_application_url" {
  description = "Private staging entry point for the frontend and API."
  value       = "https://${var.frontend_cloudfront_domain_name}"
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
