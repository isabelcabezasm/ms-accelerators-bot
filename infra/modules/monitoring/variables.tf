variable "name" {
  description = "Naming prefix used for monitoring resources."
  type        = string
}

variable "location" {
  description = "Azure region for monitoring resources."
  type        = string
}

variable "resource_group_name" {
  description = "Resource group name for resource-scoped monitoring resources."
  type        = string
}

variable "sampling_percentage" {
  description = "Application Insights telemetry sampling percentage for PII minimization."
  type        = number
  default     = 20

  validation {
    condition     = var.sampling_percentage >= 0 && var.sampling_percentage <= 100
    error_message = "sampling_percentage must be between 0 and 100."
  }
}

variable "log_analytics_sku" {
  description = "SKU for the Log Analytics workspace."
  type        = string
  default     = "PerGB2018"
}

variable "log_retention_in_days" {
  description = "Retention period for Log Analytics workspace data."
  type        = number
  default     = 30
}

variable "daily_quota_gb" {
  description = "Optional daily ingestion quota for the Log Analytics workspace."
  type        = number
  default     = null
  nullable    = true
}

variable "tags" {
  description = "Tags applied to resources created by the module."
  type        = map(string)
  default     = {}
}
