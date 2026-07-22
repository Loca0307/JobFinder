data "tls_certificate" "github_actions" {
  url = "https://token.actions.githubusercontent.com"
}

resource "aws_iam_openid_connect_provider" "github_actions" {
  url             = "https://token.actions.githubusercontent.com"
  client_id_list  = ["sts.amazonaws.com"]
  thumbprint_list = [data.tls_certificate.github_actions.certificates[0].sha1_fingerprint]
}

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
resource "aws_iam_role" "github_actions_lambda_deploy" {
  name               = "JobFinder-github-actions-lambda-deploy"
  assume_role_policy = data.aws_iam_policy_document.github_actions_assume_role.json
}
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
}

resource "aws_iam_role_policy" "github_actions_lambda_deploy" {
  name   = "lambda-code-deploy"
  role   = aws_iam_role.github_actions_lambda_deploy.id
  policy = data.aws_iam_policy_document.github_actions_lambda_deploy.json
}
