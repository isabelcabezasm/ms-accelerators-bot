variable "name" {
  description = "Name of the Key Vault."
  type        = string
}

variable "location" {
  description = "Azure region for the Key Vault."
  type        = string
}

variable "resource_group_name" {
  description = "Name of the resource group that will host the Key Vault."
  type        = string
}

variable "tenant_id" {
  description = "Azure Entra tenant ID for the Key Vault and its access policies."
  type        = string
}

variable "managed_identity_object_ids" {
  description = "Managed identity object IDs granted Key Vault access."
  type        = set(string)
  default     = []
}

variable "tags" {
  description = "Tags applied to the Key Vault."
  type        = map(string)
  default     = {}
}
