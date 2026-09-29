terraform {
  required_version = ">= 1.10"
  backend "s3" {
    bucket       = "gravv-tfstate"
    key          = "envs/staging"
    region       = "us-east-1"
    use_lockfile = true
  }
  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = ">= 5.80"
    }
  }
}
