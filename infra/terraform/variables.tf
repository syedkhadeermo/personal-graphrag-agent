variable "aws_region" {
  description = "AWS region for the portfolio deployment."
  type        = string
  default     = "eu-north-1"
}

variable "project_name" {
  description = "Lowercase name used for resource names and tags."
  type        = string
  default     = "personal-graphrag"

  validation {
    condition     = can(regex("^[a-z][a-z0-9-]{2,30}$", var.project_name))
    error_message = "project_name must be 3-31 lowercase letters, numbers, or hyphens and start with a letter."
  }
}

variable "environment" {
  description = "Environment tag for the short-lived deployment."
  type        = string
  default     = "portfolio"
}

variable "allowed_api_cidr" {
  description = "Single trusted IPv4 CIDR allowed to reach port 8000, normally your public IP with /32."
  type        = string

  validation {
    condition     = can(cidrhost(var.allowed_api_cidr, 0)) && can(regex("/32$", var.allowed_api_cidr))
    error_message = "allowed_api_cidr must be one IPv4 /32 CIDR, for example 203.0.113.10/32."
  }
}

variable "instance_type" {
  description = "EC2 size for the API demonstration."
  type        = string
  default     = "t3.small"

  validation {
    condition     = contains(["t3.micro", "t3.small"], var.instance_type)
    error_message = "instance_type must be t3.micro or t3.small for this bounded deployment."
  }
}

variable "app_repository_url" {
  description = "Public Git repository cloned by cloud-init."
  type        = string
  default     = "https://github.com/syedkhadeermo/personal-graphrag-agent.git"
}

variable "app_git_ref" {
  description = "Immutable application tag or branch deployed to EC2."
  type        = string
  default     = "v1.0.0-portfolio"
}

variable "artifact_retention_days" {
  description = "Days before runtime artifacts in the demo bucket expire."
  type        = number
  default     = 30

  validation {
    condition     = var.artifact_retention_days >= 1 && var.artifact_retention_days <= 90
    error_message = "artifact_retention_days must be between 1 and 90."
  }
}
