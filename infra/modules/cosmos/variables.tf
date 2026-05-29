variable "name" {
  description = "Name of the Cosmos DB account."
  type        = string
}

variable "location" {
  description = "Azure region for the Cosmos DB account."
  type        = string
}

variable "resource_group_name" {
  description = "Name of the resource group that will host Cosmos DB resources."
  type        = string
}

variable "database_name" {
  description = "Name of the Cosmos DB SQL database."
  type        = string
  default     = "accelerators"
}

variable "container_name" {
  description = "Name of the Cosmos DB SQL container."
  type        = string
  default     = "accelerators"
}

variable "partition_key_path" {
  description = "Partition key path for the Cosmos DB SQL container."
  type        = string
  default     = "/userId"
}

variable "managed_identity_principal_ids" {
  description = "Managed identity principal IDs granted Cosmos DB data-plane access."
  type        = set(string)
  default     = []
}

variable "tags" {
  description = "Tags applied to Cosmos DB resources."
  type        = map(string)
  default     = {}
}
