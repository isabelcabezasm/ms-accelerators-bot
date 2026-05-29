variable "environment" {
  description = "Deployment environment name."
  type        = string
  default     = "dev"

  validation {
    condition     = contains(["dev", "test", "stage", "prod"], var.environment)
    error_message = "environment must be one of: dev, test, stage, prod."
  }
}

variable "location" {
  description = "Azure region for shared infrastructure."
  type        = string
  default     = "swedencentral"
}

variable "project_name" {
  description = "Short project name used in generated resource names."
  type        = string
  default     = "ms-accelerators-bot"

  validation {
    condition     = can(regex("^[a-z0-9-]{3,24}$", var.project_name))
    error_message = "project_name must be 3-24 characters of lowercase letters, numbers, or hyphens."
  }
}

variable "tags" {
  description = "Optional extra tags merged onto all managed resources."
  type        = map(string)
  default     = {}
}
