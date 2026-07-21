
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

variable "frontend_bucket_name" {
  type    = string
  default = "job-finder-static"
}

variable "frontend_cloudfront_distribution_id" {
  type    = string
  default = "E2U4YDALK1V35D"
}

variable "frontend_cloudfront_domain_name" {
  description = "CloudFront domain used by the private staging frontend and API."
  type        = string
  default     = "d3k51jzo7lp8xb.cloudfront.net"
}
