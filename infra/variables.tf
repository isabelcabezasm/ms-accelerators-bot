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

variable "managed_identity_principal_ids" {
  description = "Managed identity principal IDs granted data-plane access to Cosmos DB and Blob Storage."
  type        = set(string)
  default     = []
}

variable "key_vault_managed_identity_object_ids" {
  description = "Managed identity object IDs granted Key Vault access policies. Defaults to managed_identity_principal_ids when empty."
  type        = set(string)
  default     = []
}

variable "tenant_id" {
  description = "Optional Azure Entra tenant ID override for the Key Vault."
  type        = string
  default     = null
  nullable    = true
}

variable "tags" {
  description = "Optional extra tags merged onto all managed resources."
  type        = map(string)
  default     = {}
}
