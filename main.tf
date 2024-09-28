terraform {
    required_providers {
        aws = {
            source  = "hashicorp/aws"
            version = "~> 4.0"
        }
        docker = {
            source  = "kreuzwerker/docker"
            version = "3.0.2"
        }
    }
}

provider "aws" {
    region = "us-east-1"
    shared_credentials_files = ["./credentials"]
    default_tags {
        tags = {
            Course       = "CSSE6400"
            Name         = "SpamOverflow"
            Automation   = "Terraform"
        }
    }
}



resource "local_file" "url" {
    content  =  "http://${aws_lb.spamoverflow.dns_name}/api/v1"
    filename = "./api.txt"
}

locals {
    image = "${docker_image.spamoverflow.name}"
    celery_image = "${docker_image.celery_worker.name}"
    database_username = "administrator"
    database_password = "verySecretPassword"
}

# data sources
data "aws_iam_role" "lab" {
  name = "LabRole"
}

# ECS cluster
data "aws_vpc" "default" {
    default = true
}

data "aws_subnets" "private" {
  filter {
    name   = "vpc-id"
    values = [data.aws_vpc.default.id]
  }
}

data "aws_ecr_authorization_token" "ecr_token" {}
provider "docker" {
    registry_auth {
        address = data.aws_ecr_authorization_token.ecr_token.proxy_endpoint
        username = data.aws_ecr_authorization_token.ecr_token.user_name
        password = data.aws_ecr_authorization_token.ecr_token.password
    }
}
resource "aws_ecr_repository" "spamoverflow" {
    name = "spamoverflow"
}
resource "aws_ecr_repository" "celery_worker" {
    name = "celery_worker"
}