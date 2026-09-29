# GitHub Actions deploys through OIDC: no long-lived cloud keys (Section 2.2).
variable "repo" { type = string } # owner/name
variable "env" { type = string }
variable "ecr_repository_arn" { type = string }
variable "apprunner_service_arns" { type = list(string) }
variable "site_bucket_arn" { type = string }
variable "distribution_arn" { type = string }

data "aws_iam_openid_connect_provider" "github" { url = "https://token.actions.githubusercontent.com" }

data "aws_iam_policy_document" "assume" {
  statement {
    actions = ["sts:AssumeRoleWithWebIdentity"]
    principals {
      type        = "Federated"
      identifiers = [data.aws_iam_openid_connect_provider.github.arn]
    }
    condition {
      test     = "StringEquals"
      variable = "token.actions.githubusercontent.com:aud"
      values   = ["sts.amazonaws.com"]
    }
    condition {
      test     = "StringLike"
      variable = "token.actions.githubusercontent.com:sub"
      values   = ["repo:${var.repo}:environment:${var.env}", "repo:${var.repo}:ref:refs/heads/main", "repo:${var.repo}:ref:refs/tags/v*"]
    }
  }
}

resource "aws_iam_role" "deploy" {
  name               = "gravv-${var.env}-github-deploy"
  assume_role_policy = data.aws_iam_policy_document.assume.json
}

data "aws_iam_policy_document" "deploy" {
  statement {
    actions   = ["ecr:GetAuthorizationToken"]
    resources = ["*"]
  }
  statement {
    actions   = ["ecr:BatchCheckLayerAvailability", "ecr:CompleteLayerUpload", "ecr:InitiateLayerUpload", "ecr:PutImage", "ecr:UploadLayerPart", "ecr:BatchGetImage", "ecr:GetDownloadUrlForLayer", "ecr:DescribeImages"]
    resources = [var.ecr_repository_arn]
  }
  statement {
    actions   = ["apprunner:UpdateService", "apprunner:DescribeService", "apprunner:StartDeployment", "apprunner:ListOperations"]
    resources = var.apprunner_service_arns
  }
  statement {
    actions   = ["iam:PassRole"]
    resources = ["*"]
    condition {
      test     = "StringEquals"
      variable = "iam:PassedToService"
      values   = ["apprunner.amazonaws.com", "build.apprunner.amazonaws.com"]
    }
  }
  statement {
    actions   = ["s3:ListBucket"]
    resources = [var.site_bucket_arn]
  }
  statement {
    actions   = ["s3:PutObject", "s3:DeleteObject", "s3:GetObject"]
    resources = ["${var.site_bucket_arn}/*"]
  }
  statement {
    actions   = ["cloudfront:CreateInvalidation"]
    resources = [var.distribution_arn]
  }
}

resource "aws_iam_role_policy" "deploy" {
  role   = aws_iam_role.deploy.id
  policy = data.aws_iam_policy_document.deploy.json
}

output "role_arn" { value = aws_iam_role.deploy.arn }
