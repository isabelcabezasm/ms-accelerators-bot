variable "name" {
  description = "Logical name for this module instance."
  type        = string
  default     = null
  nullable    = true
}

variable "location" {
  description = "Azure region when the module provisions regional resources."
  type        = string
  default     = null
  nullable    = true
}

variable "resource_group_name" {
  description = "Resource group name for resource-scoped services."
  type        = string
  default     = null
  nullable    = true
}

variable "tags" {
  description = "Tags applied to resources created by the module."
  type        = map(string)
  default     = {}
}
