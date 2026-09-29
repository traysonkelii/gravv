provider "aws" { region = var.region }

variable "region" {
  type    = string
  default = "us-east-1"
}
variable "zone_id" { type = string }
variable "certificate_arn" { type = string } # ACM certificate in us-east-1 covering the site domain
variable "supabase_url" { type = string }
variable "github_repo" { type = string }
variable "alert_email" { type = string }
variable "image_tag" {
  type    = string
  default = "bootstrap"
}

locals {
  env         = "prod"
  api_domain  = "api.gravv.app"
  site_domain = "app.gravv.app"
  secrets     = ["DATABASE_URL", "DATABASE_URL_WORKER", "SUPABASE_SECRET_KEY", "SUPABASE_JWT_SECRET", "APP_ENCRYPTION_KEY", "ANTHROPIC_API_KEY", "OPENAI_API_KEY", "SMTP_PASSWORD"]
  common_env = {
    APP_ENV                = "production"
    SUPABASE_URL           = var.supabase_url
    CORS_ORIGINS           = "https://${local.site_domain}"
    WEB_URL                = "https://${local.site_domain}"
    LLM_PROVIDER           = "anthropic"
    TRANSCRIPTION_PROVIDER = "openai"
    LOG_LEVEL              = "INFO"
    SMTP_HOST              = "email-smtp.${var.region}.amazonaws.com"
    SMTP_PORT              = "587"
    SMTP_TLS               = "true"
    SMTP_FROM              = "Gravv <no-reply@gravv.app>"
    STORAGE_BUCKET_VOICE   = "voice-notes"
    STORAGE_BUCKET_EXPORTS = "exports"
    STORAGE_BUCKET_AVATARS = "avatars"
  }
}

module "ecr" {
  source = "../../modules/ecr"
  name   = "gravv-api${local.env == "prod" ? "" : "-staging"}"
}

module "secrets" {
  source = "../../modules/secrets"
  env    = local.env
  names  = local.secrets
}

module "api" {
  source             = "../../modules/apprunner"
  name               = "gravv-api"
  image              = "${module.ecr.repository_url}:${var.image_tag}"
  env                = local.common_env
  secret_arns        = module.secrets.parameter_arns
  ecr_repository_arn = module.ecr.repository_arn
  custom_domain      = local.api_domain
  min_size           = 1
  max_size           = 10
}

module "worker" {
  source             = "../../modules/apprunner"
  name               = "gravv-worker"
  image              = "${module.ecr.repository_url}:${var.image_tag}"
  command            = ["python", "-m", "app.worker"]
  health_path        = "/healthz"
  env                = local.common_env
  secret_arns        = module.secrets.parameter_arns
  ecr_repository_arn = module.ecr.repository_arn
  min_size           = 1
  max_size           = 1
}

module "site" {
  source          = "../../modules/static-site"
  name            = "gravv-site-${local.env}"
  domain          = local.site_domain
  zone_id         = var.zone_id
  api_origin      = "https://${local.api_domain}"
  supabase_url    = var.supabase_url
  certificate_arn = var.certificate_arn
}

module "github_oidc" {
  source                 = "../../modules/github-oidc"
  repo                   = var.github_repo
  env                    = local.env
  ecr_repository_arn     = module.ecr.repository_arn
  apprunner_service_arns = [module.api.service_arn, module.worker.service_arn]
  site_bucket_arn        = "arn:aws:s3:::${module.site.bucket}"
  distribution_arn       = "arn:aws:cloudfront::${data.aws_caller_identity.current.account_id}:distribution/${module.site.distribution_id}"
}

module "alarms" {
  source              = "../../modules/alarms"
  env                 = local.env
  alert_email         = var.alert_email
  api_service_name    = "gravv-api"
  worker_service_name = "gravv-worker"
  api_log_group       = "/aws/apprunner/gravv-api/application"
  worker_log_group    = "/aws/apprunner/gravv-worker/application"
}

data "aws_caller_identity" "current" {}

output "api_url" { value = module.api.service_url }
output "api_domain_validation" { value = module.api.custom_domain_validation }
output "site_bucket" { value = module.site.bucket }
output "distribution_id" { value = module.site.distribution_id }
output "deploy_role_arn" { value = module.github_oidc.role_arn }
output "ecr_repository_url" { value = module.ecr.repository_url }
