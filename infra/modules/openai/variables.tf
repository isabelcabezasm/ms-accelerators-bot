variable "name" {
  description = "Globally unique name for the Azure OpenAI account."
  type        = string

  validation {
    condition     = can(regex("^[a-z0-9-]{2,64}$", var.name))
    error_message = "name must be 2-64 characters of lowercase letters, numbers, or hyphens."
  }
}

variable "location" {
  description = "Azure region for the Azure OpenAI account."
  type        = string
}

variable "resource_group_name" {
  description = "Resource group name for the Azure OpenAI account."
  type        = string
}

variable "sku_name" {
  description = "SKU name for the Azure OpenAI account."
  type        = string
  default     = "S0"

  validation {
    condition     = var.sku_name == "S0"
    error_message = "Only the S0 SKU is supported by this module."
  }
}

variable "custom_subdomain_name" {
  description = "Custom subdomain used by the Azure OpenAI endpoint. Defaults to the account name."
  type        = string
  default     = null
  nullable    = true

  validation {
    condition     = var.custom_subdomain_name == null || can(regex("^[a-z0-9-]{2,64}$", var.custom_subdomain_name))
    error_message = "custom_subdomain_name must be null or 2-64 characters of lowercase letters, numbers, or hyphens."
  }
}

variable "public_network_access_enabled" {
  description = "Whether public network access is enabled for the Azure OpenAI account."
  type        = bool
  default     = true
}

variable "local_auth_enabled" {
  description = "Whether local key-based authentication remains enabled for the Azure OpenAI account."
  type        = bool
  default     = false
}

variable "deployment_sku_name" {
  description = "SKU name used for model deployments."
  type        = string
  default     = "Standard"
}

variable "chat_deployment_name" {
  description = "Deployment name for the chat model."
  type        = string
  default     = "gpt-4o-mini"
}

variable "chat_model_name" {
  description = "Azure OpenAI model name for chat completions."
  type        = string
  default     = "gpt-4o-mini"
}

variable "chat_model_version" {
  description = "Version for the chat model deployment."
  type        = string
  default     = "latest"
}

variable "chat_deployment_capacity" {
  description = "Capacity units allocated to the chat model deployment."
  type        = number
  default     = 10

  validation {
    condition     = var.chat_deployment_capacity >= 1
    error_message = "chat_deployment_capacity must be at least 1."
  }
}

variable "embedding_deployment_name" {
  description = "Deployment name for the embeddings model."
  type        = string
  default     = "text-embedding-3-large"
}

variable "embedding_model_name" {
  description = "Azure OpenAI model name for embeddings."
  type        = string
  default     = "text-embedding-3-large"
}

variable "embedding_model_version" {
  description = "Version for the embeddings model deployment."
  type        = string
  default     = "latest"
}

variable "embedding_deployment_capacity" {
  description = "Capacity units allocated to the embeddings deployment."
  type        = number
  default     = 10

  validation {
    condition     = var.embedding_deployment_capacity >= 1
    error_message = "embedding_deployment_capacity must be at least 1."
  }
}

variable "embedding_dimensions" {
  description = "Embedding vector dimension exposed by the deployment."
  type        = number
  default     = 3072

  validation {
    condition     = var.embedding_dimensions > 0
    error_message = "embedding_dimensions must be greater than zero."
  }
}

variable "managed_identity_principal_ids" {
  description = "Managed identity principal IDs granted Cognitive Services OpenAI User on the account."
  type        = list(string)
  default     = []
}

variable "tags" {
  description = "Tags applied to resources created by the module."
  type        = map(string)
  default     = {}
}
