
variable "aws_region" {
  type    = string
  default = "eu-south-1"
}

variable "function_name" {
  type    = string
  default = "JobFinder-fastapi"
}

variable "jobs_table_name" {
  type    = string
  default = "Jobs"
}