resource "null_resource" "api_package" {
  triggers = {
    api_hash                = sha256(join("", [for file in fileset("${path.module}/../backend/api", "**") : filesha256("${path.module}/../backend/api/${file}")]))
    app_hash                = filesha256("${path.module}/../backend/main.py")
    package_command_version = "7"
    requirements_hash       = filesha256("${path.module}/../backend/requirements.txt")
  }

  provisioner "local-exec" {
    working_dir = path.module

    command = <<-EOT
      rm -rf build
      mkdir -p build/package
      python3 -m pip install --platform manylinux2014_x86_64 --implementation cp --python-version 3.11 --only-binary=:all: --upgrade -r ../backend/requirements.txt -t build/package
      cp ../backend/main.py build/package/main.py
      cp -R ../backend/api build/package/api
    EOT
  }
}

data "archive_file" "lambda_zip" {
  type        = "zip"
  source_dir  = "${path.module}/build/package"
  output_path = "${path.module}/build/lambda.zip"

  depends_on = [null_resource.api_package]
}

resource "aws_lambda_function" "fastapi" {
  architectures    = ["x86_64"]
  function_name    = var.function_name
  role             = aws_iam_role.lambda_role.arn
  handler          = "main.handler"
  runtime          = "python3.11"
  filename         = data.archive_file.lambda_zip.output_path
  source_code_hash = data.archive_file.lambda_zip.output_base64sha256
  timeout          = 60
  memory_size      = 512

  environment {
    variables = {
      CORS_ALLOWED_ORIGINS = "https://${var.frontend_cloudfront_domain_name}"
      DYNAMODB_JOBS_TABLE  = aws_dynamodb_table.jobs.name
    }
  }

  depends_on = [
    aws_iam_role_policy.lambda_dynamodb_access,
    aws_iam_role_policy_attachment.lambda_logs,
  ]
}

resource "aws_lambda_function_url" "fastapi" {
  function_name      = aws_lambda_function.fastapi.function_name
  authorization_type = "AWS_IAM"
}

resource "aws_lambda_permission" "allow_cloudfront_function_url" {
  statement_id           = "AllowCloudFrontFunctionUrl"
  action                 = "lambda:InvokeFunctionUrl"
  function_name          = aws_lambda_function.fastapi.function_name
  principal              = "cloudfront.amazonaws.com"
  source_arn             = "arn:aws:cloudfront::${data.aws_caller_identity.current.account_id}:distribution/${var.frontend_cloudfront_distribution_id}"
  function_url_auth_type = "AWS_IAM"
}

resource "aws_lambda_permission" "allow_cloudfront_function_url_invoke" {
  statement_id  = "AllowCloudFrontFunctionUrlInvoke"
  action        = "lambda:InvokeFunction"
  function_name = aws_lambda_function.fastapi.function_name
  principal     = "cloudfront.amazonaws.com"
  source_arn    = "arn:aws:cloudfront::${data.aws_caller_identity.current.account_id}:distribution/${var.frontend_cloudfront_distribution_id}"
}
