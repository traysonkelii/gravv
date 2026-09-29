variable "name" { type = string }
variable "image" { type = string }
variable "command" {
  type    = list(string)
  default = []
}
variable "port" {
  type    = number
  default = 8080
}
variable "cpu" {
  type    = string
  default = "1024"
}
variable "memory" {
  type    = string
  default = "2048"
}
variable "min_size" {
  type    = number
  default = 1
}
variable "max_size" {
  type    = number
  default = 10
}
variable "max_concurrency" {
  type    = number
  default = 80
}
variable "health_path" {
  type    = string
  default = "/readyz"
}
variable "env" { type = map(string) }
variable "secret_arns" { type = map(string) }
variable "ecr_repository_arn" { type = string }
variable "custom_domain" {
  type    = string
  default = ""
}

data "aws_iam_policy_document" "access_assume" {
  statement {
    actions = ["sts:AssumeRole"]
    principals {
      type        = "Service"
      identifiers = ["build.apprunner.amazonaws.com"]
    }
  }
}

resource "aws_iam_role" "access" {
  name               = "${var.name}-ecr-access"
  assume_role_policy = data.aws_iam_policy_document.access_assume.json
}

resource "aws_iam_role_policy_attachment" "access_ecr" {
  role       = aws_iam_role.access.name
  policy_arn = "arn:aws:iam::aws:policy/service-role/AWSAppRunnerServicePolicyForECRAccess"
}

data "aws_iam_policy_document" "instance_assume" {
  statement {
    actions = ["sts:AssumeRole"]
    principals {
      type        = "Service"
      identifiers = ["tasks.apprunner.amazonaws.com"]
    }
  }
}

resource "aws_iam_role" "instance" {
  name               = "${var.name}-instance"
  assume_role_policy = data.aws_iam_policy_document.instance_assume.json
}

data "aws_iam_policy_document" "instance" {
  statement {
    actions   = ["ssm:GetParameters", "ssm:GetParameter"]
    resources = values(var.secret_arns)
  }
  statement {
    actions   = ["kms:Decrypt"]
    resources = ["*"]
    condition {
      test     = "StringEquals"
      variable = "kms:ViaService"
      values   = ["ssm.${data.aws_region.current.region}.amazonaws.com"]
    }
  }
}

resource "aws_iam_role_policy" "instance" {
  role   = aws_iam_role.instance.id
  policy = data.aws_iam_policy_document.instance.json
}

resource "aws_apprunner_auto_scaling_configuration_version" "this" {
  auto_scaling_configuration_name = substr("${var.name}-asc", 0, 32)
  max_concurrency                 = var.max_concurrency
  min_size                        = var.min_size
  max_size                        = var.max_size
}

resource "aws_apprunner_service" "this" {
  service_name                   = var.name
  auto_scaling_configuration_arn = aws_apprunner_auto_scaling_configuration_version.this.arn

  source_configuration {
    auto_deployments_enabled = false
    authentication_configuration { access_role_arn = aws_iam_role.access.arn }
    image_repository {
      image_identifier      = var.image
      image_repository_type = "ECR"
      image_configuration {
        port                          = tostring(var.port)
        start_command                 = length(var.command) > 0 ? join(" ", var.command) : null
        runtime_environment_variables = var.env
        runtime_environment_secrets   = var.secret_arns
      }
    }
  }

  instance_configuration {
    cpu               = var.cpu
    memory            = var.memory
    instance_role_arn = aws_iam_role.instance.arn
  }

  health_check_configuration {
    protocol            = "HTTP"
    path                = var.health_path
    interval            = 10
    timeout             = 5
    healthy_threshold   = 1
    unhealthy_threshold = 5
  }

  lifecycle { ignore_changes = [source_configuration[0].image_repository[0].image_identifier] }
}

resource "aws_apprunner_custom_domain_association" "this" {
  count       = var.custom_domain == "" ? 0 : 1
  domain_name = var.custom_domain
  service_arn = aws_apprunner_service.this.arn
}

data "aws_region" "current" {}

output "service_arn" { value = aws_apprunner_service.this.arn }
output "service_url" { value = aws_apprunner_service.this.service_url }
output "custom_domain_validation" {
  value = var.custom_domain == "" ? [] : aws_apprunner_custom_domain_association.this[0].certificate_validation_records
}
