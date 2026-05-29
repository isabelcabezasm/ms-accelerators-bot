variable "name" {
  description = "Name of the Static Web App."
  type        = string
}

variable "location" {
  description = "Azure region for the Static Web App."
  type        = string
}

variable "resource_group_name" {
  description = "Resource group name for the Static Web App."
  type        = string
}

variable "sku_tier" {
  description = "SKU tier for the Static Web App. Use Standard for custom auth and SLA support."
  type        = string
  default     = "Standard"
}

variable "sku_size" {
  description = "SKU size for the Static Web App."
  type        = string
  default     = "Standard"
}

variable "app_settings" {
  description = "Application settings for the Static Web App."
  type        = map(string)
  default     = {}
}

variable "tags" {
  description = "Tags applied to resources created by the module."
  type        = map(string)
  default     = {}
}
