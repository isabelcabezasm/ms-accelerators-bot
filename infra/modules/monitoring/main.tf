locals {
  application_insights_name    = "${var.name}-appi"
  log_analytics_workspace_name = "${var.name}-law"
}

resource "azurerm_log_analytics_workspace" "this" {
  name                = local.log_analytics_workspace_name
  location            = var.location
  resource_group_name = var.resource_group_name
  sku                 = var.log_analytics_sku
  retention_in_days   = var.log_retention_in_days
  daily_quota_gb      = var.daily_quota_gb
  tags                = var.tags
}

resource "azurerm_application_insights" "this" {
  name                = local.application_insights_name
  location            = var.location
  resource_group_name = var.resource_group_name
  workspace_id        = azurerm_log_analytics_workspace.this.id
  application_type    = "web"
  sampling_percentage = var.sampling_percentage

  # Keep IP masking enabled so raw client IPs are not persisted with telemetry.
  disable_ip_masking = false
  tags               = var.tags
}
