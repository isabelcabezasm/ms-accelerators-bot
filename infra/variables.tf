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

variable "front_door_enabled" {
  description = "Whether to provision Azure Front Door resources from this root module."
  type        = bool
  default     = false
}

variable "front_door_sku_name" {
  description = "Azure Front Door SKU. Premium is required for OWASP managed rules and bot protection."
  type        = string
  default     = "Premium_AzureFrontDoor"

  validation {
    condition     = contains(["Standard_AzureFrontDoor", "Premium_AzureFrontDoor"], var.front_door_sku_name)
    error_message = "front_door_sku_name must be Standard_AzureFrontDoor or Premium_AzureFrontDoor."
  }
}

variable "front_door_response_timeout_seconds" {
  description = "Front Door origin response timeout in seconds."
  type        = number
  default     = 120
}

variable "front_door_endpoint_name" {
  description = "Optional globally unique Front Door endpoint name override."
  type        = string
  default     = null
  nullable    = true
}

variable "front_door_waf_mode" {
  description = "WAF operating mode for Front Door."
  type        = string
  default     = "Prevention"

  validation {
    condition     = contains(["Detection", "Prevention"], var.front_door_waf_mode)
    error_message = "front_door_waf_mode must be Detection or Prevention."
  }
}

variable "front_door_swa_origin" {
  description = "Origin configuration for the Static Web Apps frontend."
  type = object({
    host_name                        = string
    origin_host_header               = optional(string)
    priority                         = optional(number, 1)
    weight                           = optional(number, 1000)
    health_probe_path                = optional(string, "/")
    health_probe_protocol            = optional(string, "Https")
    health_probe_request_type        = optional(string, "HEAD")
    health_probe_interval_in_seconds = optional(number, 120)
  })
  default = {
    host_name = "example.azurestaticapps.net"
  }
}

variable "front_door_container_app_origin" {
  description = "Origin configuration for the Container Apps API."
  type = object({
    host_name                        = string
    origin_host_header               = optional(string)
    priority                         = optional(number, 1)
    weight                           = optional(number, 1000)
    health_probe_path                = optional(string, "/healthz")
    health_probe_protocol            = optional(string, "Https")
    health_probe_request_type        = optional(string, "HEAD")
    health_probe_interval_in_seconds = optional(number, 120)
  })
  default = {
    host_name = "example.swedencentral.azurecontainerapps.io"
  }
}

variable "front_door_custom_domains" {
  description = "Optional custom domains attached to every Front Door route."
  type = map(object({
    host_name               = string
    dns_zone_id             = optional(string)
    tls_certificate_type    = optional(string, "ManagedCertificate")
    minimum_tls_version     = optional(string, "TLS12")
    cdn_frontdoor_secret_id = optional(string)
  }))
  default = {}
}
