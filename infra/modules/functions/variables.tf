variable "name" {
  description = "Name of the Function App."
  type        = string
}

variable "location" {
  description = "Azure region for the Function App resources."
  type        = string
}

variable "resource_group_name" {
  description = "Resource group name for the Function App resources."
  type        = string
}

variable "storage_account_name" {
  description = "Optional storage account name for the Function App. Defaults to a sanitized name derived from the app name."
  type        = string
  default     = null
  nullable    = true
}

variable "service_plan_sku" {
  description = "SKU for the App Service plan. Use Y1 for Linux Consumption."
  type        = string
  default     = "Y1"
}

variable "python_version" {
  description = "Python runtime version for the Function App."
  type        = string
  default     = "3.12"
}

variable "functions_extension_version" {
  description = "Azure Functions runtime version."
  type        = string
  default     = "~4"
}

variable "https_only" {
  description = "Whether to require HTTPS for the Function App."
  type        = bool
  default     = true
}

variable "public_network_access_enabled" {
  description = "Whether public network access is enabled for the Function App."
  type        = bool
  default     = true
}

variable "app_settings" {
  description = "Additional application settings for the Function App."
  type        = map(string)
  default     = {}
}

variable "tags" {
  description = "Tags applied to resources created by the module."
  type        = map(string)
  default     = {}
}
