locals {
  frontend_cloudfront_distribution_arn = "arn:aws:cloudfront::${data.aws_caller_identity.current.account_id}:distribution/${var.frontend_cloudfront_distribution_id}"
}

# Attach this OAC to the Lambda Function URL origin in the existing CloudFront
# distribution. The distribution itself must be imported before Terraform can
# safely manage its origins and cache behaviors.
resource "aws_cloudfront_origin_access_control" "lambda" {
  name                              = "jobfinder-lambda-oac"
  description                       = "SigV4 access from the JobFinder CloudFront distribution to its Lambda Function URL"
  origin_access_control_origin_type = "lambda"
  signing_behavior                  = "always"
  signing_protocol                  = "sigv4"
}
