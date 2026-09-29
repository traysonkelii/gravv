# SSM SecureString parameters. Values are supplied out of band:
#   aws ssm put-parameter --name /gravv/staging/DATABASE_URL --type SecureString --value '...' --overwrite
# Terraform records names only, so secrets never enter state or the repository.
variable "env" { type = string }
variable "names" { type = list(string) }

locals { prefix = "/gravv/${var.env}" }

output "prefix" { value = local.prefix }
output "parameter_arns" {
  value = { for n in var.names : n => "arn:aws:ssm:${data.aws_region.current.region}:${data.aws_caller_identity.current.account_id}:parameter${local.prefix}/${n}" }
}

data "aws_region" "current" {}
data "aws_caller_identity" "current" {}
