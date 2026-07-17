// --------- Mainly to setup IAM role for the workflow to use ------------


// Extracts current certificate from github OIDC
// so Github action can issue  JWT token
data "tls_certificate" "github_actions" {
  url = "https://token.actions.githubusercontent.com"
}

// Register github action as a trusted entity provider to AWS, to accept 
// the JWT tokens
resource "aws_iam_openid_connect_provider" "github_actions" {
  url             = "https://token.actions.githubusercontent.com"
  client_id_list  = ["sts.amazonaws.com"]
  thumbprint_list = [data.tls_certificate.github_actions.certificates[0].sha1_fingerprint]
}

// Defines the condition for the Action to assume a IAM role for security
data "aws_iam_policy_document" "github_actions_assume_role" {
  statement {
    actions = ["sts:AssumeRoleWithWebIdentity"]
    effect  = "Allow"

    principals {
      type        = "Federated"
      identifiers = [aws_iam_openid_connect_provider.github_actions.arn]
    }

    condition {
      test     = "StringEquals"
      variable = "token.actions.githubusercontent.com:aud"
      values   = ["sts.amazonaws.com"]
    }

    condition {
      test     = "StringEquals"
      variable = "token.actions.githubusercontent.com:sub"
      values   = ["repo:Loca0307/JobFinder:ref:refs/heads/main"]
    }
  }
}


// Created the actual IAM role that the Action 
// needs to assume with the previously defined rules
resource "aws_iam_role" "github_actions_lambda_deploy" {
  name               = "JobFinder-github-actions-lambda-deploy"
  assume_role_policy = data.aws_iam_policy_document.github_actions_assume_role.json
}


// Attaches the necessary policie to the IAM role
data "aws_iam_policy_document" "github_actions_lambda_deploy" {
  statement {
    actions = [
      "lambda:GetFunctionConfiguration",
      "lambda:GetFunctionUrlConfig",
      "lambda:UpdateFunctionCode",
    ]
    effect    = "Allow"
    resources = [aws_lambda_function.fastapi.arn]
  }

  statement {
    actions = [
      "s3:GetBucketLocation",
      "s3:ListBucket",
    ]
    effect    = "Allow"
    resources = ["arn:aws:s3:::job-finder-static"]
  }

  statement {
    actions = [
      "s3:DeleteObject",
      "s3:GetObject",
      "s3:PutObject",
    ]
    effect    = "Allow"
    resources = ["arn:aws:s3:::job-finder-static/out/*"]
  }

  statement {
    actions   = ["cloudfront:CreateInvalidation"]
    effect    = "Allow"
    resources = ["arn:aws:cloudfront::637560253280:distribution/E2U4YDALK1V35D"]
  }
}

resource "aws_iam_role_policy" "github_actions_lambda_deploy" {
  name   = "lambda-code-deploy"
  role   = aws_iam_role.github_actions_lambda_deploy.id
  policy = data.aws_iam_policy_document.github_actions_lambda_deploy.json
}
