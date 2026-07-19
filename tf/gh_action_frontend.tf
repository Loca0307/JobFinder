data "aws_caller_identity" "current" {}

resource "aws_iam_role" "github_actions_frontend_deploy" {
  name               = "JobFinder-github-actions-frontend-deploy"
  assume_role_policy = data.aws_iam_policy_document.github_actions_assume_role.json
}

data "aws_iam_policy_document" "github_actions_frontend_deploy" {
  statement {
    actions = [
      "s3:GetBucketLocation",
      "s3:ListBucket",
    ]
    resources = ["arn:aws:s3:::${var.frontend_bucket_name}"]
  }

  statement {
    actions = [
      "s3:DeleteObject",
      "s3:GetObject",
      "s3:PutObject",
    ]
    resources = ["arn:aws:s3:::${var.frontend_bucket_name}/out/*"]
  }

  statement {
    actions = ["cloudfront:CreateInvalidation"]
    resources = [
      "arn:aws:cloudfront::${data.aws_caller_identity.current.account_id}:distribution/${var.frontend_cloudfront_distribution_id}"
    ]
  }
}

resource "aws_iam_role_policy" "github_actions_frontend_deploy" {
  name   = "frontend-deploy"
  role   = aws_iam_role.github_actions_frontend_deploy.id
  policy = data.aws_iam_policy_document.github_actions_frontend_deploy.json
}
