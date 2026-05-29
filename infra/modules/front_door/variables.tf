variable "name" {
  description = "Base name used for Front Door resources."
  type        = string
}

variable "resource_group_name" {
  description = "Resource group where the Front Door profile and WAF policy are created."
  type        = string
}

variable "sku_name" {
  description = "Front Door SKU. Premium is required for managed OWASP and bot protection rules."
  type        = string
  default     = "Premium_AzureFrontDoor"

  validation {
    condition     = contains(["Standard_AzureFrontDoor", "Premium_AzureFrontDoor"], var.sku_name)
    error_message = "sku_name must be Standard_AzureFrontDoor or Premium_AzureFrontDoor."
  }
}

variable "response_timeout_seconds" {
  description = "Front Door origin response timeout in seconds."
  type        = number
  default     = 120
}

variable "endpoint_name" {
  description = "Optional globally unique Front Door endpoint name override."
  type        = string
  default     = null
  nullable    = true
}

variable "waf_mode" {
  description = "WAF operating mode."
  type        = string
  default     = "Prevention"

  validation {
    condition     = contains(["Detection", "Prevention"], var.waf_mode)
    error_message = "waf_mode must be Detection or Prevention."
  }
}

variable "swa_origin" {
  description = "Origin configuration for Azure Static Web Apps."
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
}

variable "container_app_origin" {
  description = "Origin configuration for the Container Apps-backed API."
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
}

variable "api_patterns_to_match" {
  description = "Path patterns routed to the Container Apps API origin."
  type        = list(string)
  default = [
    "/api/*",
    "/chat",
    "/chat/*",
    "/search",
    "/search/*",
    "/accelerators",
    "/accelerators/*",
    "/healthz",
    "/healthz/*",
  ]
}

variable "static_asset_patterns_to_match" {
  description = "Path patterns for static assets served from Static Web Apps with caching enabled."
  type        = list(string)
  default = [
    "/assets/*",
    "/*.css",
    "/*.js",
    "/*.mjs",
    "/*.json",
    "/*.map",
    "/*.svg",
    "/*.ico",
    "/*.png",
    "/*.jpg",
    "/*.jpeg",
    "/*.gif",
    "/*.webp",
    "/*.woff",
    "/*.woff2",
    "/*.ttf",
  ]
}

variable "web_patterns_to_match" {
  description = "Fallback path patterns routed to the Static Web Apps origin."
  type        = list(string)
  default     = ["/*"]
}

variable "static_asset_cache_query_string_behavior" {
  description = "How Front Door caches static asset requests with query strings."
  type        = string
  default     = "IgnoreQueryString"

  validation {
    condition = contains([
      "IgnoreQueryString",
      "IgnoreSpecifiedQueryStrings",
      "IncludeSpecifiedQueryStrings",
      "UseQueryString",
    ], var.static_asset_cache_query_string_behavior)
    error_message = "static_asset_cache_query_string_behavior must be a supported Front Door cache mode."
  }
}

variable "static_asset_cache_query_strings" {
  description = "Optional query string allow/deny list used by the cache policy."
  type        = list(string)
  default     = []
}

variable "static_asset_content_types_to_compress" {
  description = "Compressible content types for static assets."
  type        = list(string)
  default = [
    "application/javascript",
    "application/json",
    "application/xml",
    "font/otf",
    "font/ttf",
    "image/svg+xml",
    "text/css",
    "text/html",
    "text/javascript",
    "text/plain",
    "text/xml",
  ]
}

variable "custom_domains" {
  description = "Optional custom domains to attach to all Front Door routes."
  type = map(object({
    host_name               = string
    dns_zone_id             = optional(string)
    tls_certificate_type    = optional(string, "ManagedCertificate")
    minimum_tls_version     = optional(string, "TLS12")
    cdn_frontdoor_secret_id = optional(string)
  }))
  default = {}
}

variable "tags" {
  description = "Tags applied to resources created by the module."
  type        = map(string)
  default     = {}
}
