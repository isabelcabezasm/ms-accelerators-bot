output "profile_id" {
  description = "Resource ID of the Front Door profile."
  value       = azurerm_cdn_frontdoor_profile.this.id
}

output "profile_name" {
  description = "Name of the Front Door profile."
  value       = azurerm_cdn_frontdoor_profile.this.name
}

output "endpoint_id" {
  description = "Resource ID of the Front Door endpoint."
  value       = azurerm_cdn_frontdoor_endpoint.this.id
}

output "endpoint_host_name" {
  description = "Default host name assigned to the Front Door endpoint."
  value       = azurerm_cdn_frontdoor_endpoint.this.host_name
}

output "waf_policy_id" {
  description = "Resource ID of the Front Door WAF policy."
  value       = azurerm_cdn_frontdoor_firewall_policy.this.id
}

output "security_policy_id" {
  description = "Resource ID of the Front Door security policy."
  value       = azurerm_cdn_frontdoor_security_policy.this.id
}

output "origin_group_ids" {
  description = "Origin group IDs keyed by workload."
  value = {
    swa           = azurerm_cdn_frontdoor_origin_group.swa.id
    container_app = azurerm_cdn_frontdoor_origin_group.container_app.id
  }
}

output "route_ids" {
  description = "Route IDs keyed by route purpose."
  value = {
    api           = azurerm_cdn_frontdoor_route.api.id
    static_assets = azurerm_cdn_frontdoor_route.static_assets.id
    web           = azurerm_cdn_frontdoor_route.web.id
  }
}

output "custom_domain_validation_tokens" {
  description = "Validation tokens for any configured custom domains."
  value = {
    for key, domain in azurerm_cdn_frontdoor_custom_domain.this : key => domain.validation_token
  }
}
