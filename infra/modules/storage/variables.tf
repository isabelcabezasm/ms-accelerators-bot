variable "name" {
  description = "Name of the storage account."
  type        = string
}

variable "location" {
  description = "Azure region for the storage account."
  type        = string
}

variable "resource_group_name" {
  description = "Name of the resource group that will host storage resources."
  type        = string
}

variable "container_name" {
  description = "Name of the blob container for raw snapshots."
  type        = string
  default     = "raw-snapshots"
}

variable "managed_identity_principal_ids" {
  description = "Managed identity principal IDs granted blob reader access."
  type        = set(string)
  default     = []
}

variable "tags" {
  description = "Tags applied to storage resources."
  type        = map(string)
  default     = {}
}
