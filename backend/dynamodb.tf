terraform {
  required_version = ">= 1.5.0"

  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 5.0"
    }
  }
}

variable "aws_region" {
  type        = string
  default     = "eu-south-1"
}

variable "jobs_table_name" {
  type        = string
  default     = "Jobs"
}

provider "aws" {
  region = var.aws_region
}

resource "aws_dynamodb_table" "jobs" {
  name         = var.jobs_table_name
  billing_mode = "PAY_PER_REQUEST"
  hash_key     = "PK"
  range_key    = "SK"

  attribute {
    name = "PK"
    type = "S"
  }


  point_in_time_recovery {
    enabled = true
  }

  server_side_encryption {
    enabled = true
  }

  tags = {
    Application = "JobFinder"
    ManagedBy   = "Terraform"
  }
}

 
output "jobs_table_name" {
  description = "Set this value as DYNAMODB_JOBS_TABLE for the backend Lambda."
  value       = aws_dynamodb_table.jobs.name
}

output "jobs_table_arn" {
  description = "DynamoDB jobs table ARN."
  value       = aws_dynamodb_table.jobs.arn
}

output "jobs_table_access_policy_json" {
  description = "IAM policy JSON to attach to the backend Lambda role."
  value       = data.aws_iam_policy_document.jobs_table_access.json
}
