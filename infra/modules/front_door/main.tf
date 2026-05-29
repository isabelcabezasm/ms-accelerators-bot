locals {
  resource_prefix = substr(
    trim(replace(lower(var.name), "/[^a-z0-9-]/", "-"), "-"),
    0,
    40,
  )
  endpoint_name      = substr(coalesce(var.endpoint_name, "${local.resource_prefix}-ep"), 0, 50)
  custom_domain_ids  = [for domain in values(azurerm_cdn_frontdoor_custom_domain.this) : domain.id]
  rate_limit_message = base64encode(jsonencode({ message = "Rate limit exceeded." }))
}

resource "azurerm_cdn_frontdoor_profile" "this" {
  name                     = "${local.resource_prefix}-profile"
  resource_group_name      = var.resource_group_name
  sku_name                 = var.sku_name
  response_timeout_seconds = var.response_timeout_seconds
  tags                     = var.tags
}

resource "azurerm_cdn_frontdoor_endpoint" "this" {
  name                     = local.endpoint_name
  cdn_frontdoor_profile_id = azurerm_cdn_frontdoor_profile.this.id
  enabled                  = true
  tags                     = var.tags
}

resource "azurerm_cdn_frontdoor_origin_group" "swa" {
  name                     = "${local.resource_prefix}-swa-og"
  cdn_frontdoor_profile_id = azurerm_cdn_frontdoor_profile.this.id
  session_affinity_enabled = false

  restore_traffic_time_to_healed_or_new_endpoint_in_minutes = 10

  load_balancing {
    additional_latency_in_milliseconds = 0
    sample_size                        = 4
    successful_samples_required        = 3
  }

  health_probe {
    interval_in_seconds = var.swa_origin.health_probe_interval_in_seconds
    path                = var.swa_origin.health_probe_path
    protocol            = var.swa_origin.health_probe_protocol
    request_type        = var.swa_origin.health_probe_request_type
  }
}

resource "azurerm_cdn_frontdoor_origin_group" "container_app" {
  name                     = "${local.resource_prefix}-api-og"
  cdn_frontdoor_profile_id = azurerm_cdn_frontdoor_profile.this.id
  session_affinity_enabled = false

  restore_traffic_time_to_healed_or_new_endpoint_in_minutes = 10

  load_balancing {
    additional_latency_in_milliseconds = 0
    sample_size                        = 4
    successful_samples_required        = 3
  }

  health_probe {
    interval_in_seconds = var.container_app_origin.health_probe_interval_in_seconds
    path                = var.container_app_origin.health_probe_path
    protocol            = var.container_app_origin.health_probe_protocol
    request_type        = var.container_app_origin.health_probe_request_type
  }
}

resource "azurerm_cdn_frontdoor_origin" "swa" {
  name                          = "${local.resource_prefix}-swa-origin"
  cdn_frontdoor_origin_group_id = azurerm_cdn_frontdoor_origin_group.swa.id
  enabled                       = true

  certificate_name_check_enabled = true
  host_name                      = var.swa_origin.host_name
  origin_host_header             = coalesce(var.swa_origin.origin_host_header, var.swa_origin.host_name)
  http_port                      = 80
  https_port                     = 443
  priority                       = var.swa_origin.priority
  weight                         = var.swa_origin.weight
}

resource "azurerm_cdn_frontdoor_origin" "container_app" {
  name                          = "${local.resource_prefix}-api-origin"
  cdn_frontdoor_origin_group_id = azurerm_cdn_frontdoor_origin_group.container_app.id
  enabled                       = true

  certificate_name_check_enabled = true
  host_name                      = var.container_app_origin.host_name
  origin_host_header             = coalesce(var.container_app_origin.origin_host_header, var.container_app_origin.host_name)
  http_port                      = 80
  https_port                     = 443
  priority                       = var.container_app_origin.priority
  weight                         = var.container_app_origin.weight
}

resource "azurerm_cdn_frontdoor_custom_domain" "this" {
  for_each = var.custom_domains

  name                     = substr("${local.resource_prefix}-${trim(replace(lower(each.key), "/[^a-z0-9-]/", "-"), "-")}", 0, 90)
  cdn_frontdoor_profile_id = azurerm_cdn_frontdoor_profile.this.id
  host_name                = each.value.host_name
  dns_zone_id              = each.value.dns_zone_id

  tls {
    certificate_type        = each.value.tls_certificate_type
    minimum_tls_version     = each.value.minimum_tls_version
    cdn_frontdoor_secret_id = each.value.tls_certificate_type == "CustomerCertificate" ? each.value.cdn_frontdoor_secret_id : null
  }
}

resource "azurerm_cdn_frontdoor_firewall_policy" "this" {
  name                              = "${local.resource_prefix}-waf"
  resource_group_name               = var.resource_group_name
  sku_name                          = var.sku_name
  enabled                           = true
  mode                              = var.waf_mode
  custom_block_response_status_code = 429
  custom_block_response_body        = local.rate_limit_message

  custom_rule {
    name                           = "chat-rate-limit"
    action                         = "Block"
    enabled                        = true
    priority                       = 10
    rate_limit_duration_in_minutes = 1
    rate_limit_threshold           = 30
    type                           = "RateLimitRule"

    match_condition {
      match_variable     = "RequestUri"
      operator           = "BeginsWith"
      negation_condition = false
      # Use "/chat/" prefix (not "/chat") to avoid matching unrelated paths
      # like /chatbot or /chatroom. Exact "/chat" path is also covered by
      # the /chat/* API route pattern.
      match_values = ["/chat/"]
    }
  }

  custom_rule {
    name                           = "anonymous-search-rate-limit"
    action                         = "Block"
    enabled                        = true
    priority                       = 20
    rate_limit_duration_in_minutes = 1
    rate_limit_threshold           = 10
    type                           = "RateLimitRule"

    match_condition {
      match_variable     = "RequestUri"
      operator           = "BeginsWith"
      negation_condition = false
      match_values       = ["/search"]
    }

    match_condition {
      match_variable     = "RequestHeader"
      selector           = "Authorization"
      operator           = "BeginsWith"
      negation_condition = true
      match_values       = ["Bearer "]
      transforms         = ["Trim"]
    }
  }

  # NOTE: OWASP and Bot Manager managed rules are only supported on the
  # Premium_AzureFrontDoor SKU. These blocks are silently omitted on
  # Standard SKU. Upgrade to Premium to enable managed rule protection.
  dynamic "managed_rule" {
    for_each = var.sku_name == "Premium_AzureFrontDoor" ? [1] : []

    content {
      type    = "Microsoft_DefaultRuleSet"
      version = "2.1"
      action  = "Block"
    }
  }

  dynamic "managed_rule" {
    for_each = var.sku_name == "Premium_AzureFrontDoor" ? [1] : []

    content {
      type    = "Microsoft_BotManagerRuleSet"
      version = "1.1"
      action  = "Block"
    }
  }

  tags = var.tags
}

resource "azurerm_cdn_frontdoor_security_policy" "this" {
  name                     = "${local.resource_prefix}-security"
  cdn_frontdoor_profile_id = azurerm_cdn_frontdoor_profile.this.id

  security_policies {
    firewall {
      cdn_frontdoor_firewall_policy_id = azurerm_cdn_frontdoor_firewall_policy.this.id

      association {
        patterns_to_match = ["/*"]

        domain {
          cdn_frontdoor_domain_id = azurerm_cdn_frontdoor_endpoint.this.id
        }

        dynamic "domain" {
          for_each = azurerm_cdn_frontdoor_custom_domain.this

          content {
            cdn_frontdoor_domain_id = domain.value.id
          }
        }
      }
    }
  }
}

resource "azurerm_cdn_frontdoor_route" "api" {
  name                          = "${local.resource_prefix}-api"
  cdn_frontdoor_endpoint_id     = azurerm_cdn_frontdoor_endpoint.this.id
  cdn_frontdoor_origin_group_id = azurerm_cdn_frontdoor_origin_group.container_app.id
  cdn_frontdoor_origin_ids      = [azurerm_cdn_frontdoor_origin.container_app.id]
  enabled                       = true

  forwarding_protocol             = "HttpsOnly"
  https_redirect_enabled          = true
  patterns_to_match               = var.api_patterns_to_match
  supported_protocols             = ["Http", "Https"]
  cdn_frontdoor_custom_domain_ids = local.custom_domain_ids
  link_to_default_domain          = true
}

resource "azurerm_cdn_frontdoor_route" "static_assets" {
  name                          = "${local.resource_prefix}-static"
  cdn_frontdoor_endpoint_id     = azurerm_cdn_frontdoor_endpoint.this.id
  cdn_frontdoor_origin_group_id = azurerm_cdn_frontdoor_origin_group.swa.id
  cdn_frontdoor_origin_ids      = [azurerm_cdn_frontdoor_origin.swa.id]
  enabled                       = true

  forwarding_protocol             = "HttpsOnly"
  https_redirect_enabled          = true
  patterns_to_match               = var.static_asset_patterns_to_match
  supported_protocols             = ["Http", "Https"]
  cdn_frontdoor_custom_domain_ids = local.custom_domain_ids
  link_to_default_domain          = true

  cache {
    query_string_caching_behavior = var.static_asset_cache_query_string_behavior
    query_strings                 = var.static_asset_cache_query_strings
    compression_enabled           = true
    content_types_to_compress     = var.static_asset_content_types_to_compress
  }
}

resource "azurerm_cdn_frontdoor_route" "web" {
  name                          = "${local.resource_prefix}-web"
  cdn_frontdoor_endpoint_id     = azurerm_cdn_frontdoor_endpoint.this.id
  cdn_frontdoor_origin_group_id = azurerm_cdn_frontdoor_origin_group.swa.id
  cdn_frontdoor_origin_ids      = [azurerm_cdn_frontdoor_origin.swa.id]
  enabled                       = true

  forwarding_protocol             = "HttpsOnly"
  https_redirect_enabled          = true
  patterns_to_match               = var.web_patterns_to_match
  supported_protocols             = ["Http", "Https"]
  cdn_frontdoor_custom_domain_ids = local.custom_domain_ids
  link_to_default_domain          = true
}

resource "azurerm_cdn_frontdoor_custom_domain_association" "this" {
  for_each = azurerm_cdn_frontdoor_custom_domain.this

  cdn_frontdoor_custom_domain_id = each.value.id
  cdn_frontdoor_route_ids = [
    azurerm_cdn_frontdoor_route.api.id,
    azurerm_cdn_frontdoor_route.static_assets.id,
    azurerm_cdn_frontdoor_route.web.id,
  ]
}
