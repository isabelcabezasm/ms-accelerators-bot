variable "name" {
  description = "Globally unique name for the Azure AI Search service."
  type        = string

  validation {
    condition     = can(regex("^[a-z0-9-]{2,60}$", var.name))
    error_message = "name must be 2-60 characters of lowercase letters, numbers, or hyphens."
  }
}

variable "location" {
  description = "Azure region for the Azure AI Search service."
  type        = string
}

variable "resource_group_name" {
  description = "Resource group name for the Azure AI Search service."
  type        = string
}

variable "sku" {
  description = "Azure AI Search SKU."
  type        = string
  default     = "basic"

  validation {
    condition     = lower(var.sku) == "basic"
    error_message = "Only the Basic SKU is supported by this module."
  }
}

variable "replica_count" {
  description = "Replica count for the Azure AI Search service."
  type        = number
  default     = 1

  validation {
    condition     = var.replica_count >= 1
    error_message = "replica_count must be at least 1."
  }
}

variable "partition_count" {
  description = "Partition count for the Azure AI Search service."
  type        = number
  default     = 1

  validation {
    condition     = var.partition_count >= 1
    error_message = "partition_count must be at least 1."
  }
}

variable "semantic_search_sku" {
  description = "Semantic search billing tier for the service."
  type        = string
  default     = "free"

  validation {
    condition     = contains(["free", "standard"], lower(var.semantic_search_sku))
    error_message = "semantic_search_sku must be either free or standard."
  }
}

variable "public_network_access_enabled" {
  description = "Whether public network access is enabled for the search service."
  type        = bool
  default     = true
}

variable "local_authentication_enabled" {
  description = "Whether API key authentication remains enabled for the search service."
  type        = bool
  default     = false
}

variable "authentication_failure_mode" {
  description = "AAD authentication challenge behavior when local authentication is enabled."
  type        = string
  default     = "http401WithBearerChallenge"

  validation {
    condition     = contains(["http401WithBearerChallenge", "http403"], var.authentication_failure_mode)
    error_message = "authentication_failure_mode must be either http401WithBearerChallenge or http403."
  }
}

variable "index_name" {
  description = "Name of the placeholder hybrid search index."
  type        = string
  default     = "accelerators-index"

  validation {
    condition     = can(regex("^[A-Za-z0-9][A-Za-z0-9_-]{1,127}$", var.index_name))
    error_message = "index_name must be 2-128 characters and start with a letter or number."
  }
}

variable "semantic_configuration_name" {
  description = "Name of the semantic configuration on the placeholder index."
  type        = string
  default     = "default"
}

variable "embedding_dimensions" {
  description = "Embedding vector dimension for the placeholder index."
  type        = number
  default     = 3072

  validation {
    condition     = var.embedding_dimensions > 0
    error_message = "embedding_dimensions must be greater than zero."
  }
}

variable "managed_identity_principal_ids" {
  description = "Managed identity principal IDs granted Search Index Data Reader on the service."
  type        = list(string)
  default     = []
}

variable "tags" {
  description = "Tags applied to resources created by the module."
  type        = map(string)
  default     = {}
}
