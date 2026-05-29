locals {
  storage_account_name = coalesce(
    var.storage_account_name,
    substr(lower("${replace(var.name, "-", "")}${substr(md5(var.name), 0, 6)}"), 0, 24)
  )
}

resource "azurerm_storage_account" "this" {
  name                            = local.storage_account_name
  resource_group_name             = var.resource_group_name
  location                        = var.location
  account_tier                    = "Standard"
  account_replication_type        = "LRS"
  account_kind                    = "StorageV2"
  min_tls_version                 = "TLS1_2"
  https_traffic_only_enabled      = true
  allow_nested_items_to_be_public = false
  tags                            = var.tags
}

resource "azurerm_service_plan" "this" {
  name                = "${var.name}-plan"
  location            = var.location
  resource_group_name = var.resource_group_name
  os_type             = "Linux"
  sku_name            = var.service_plan_sku
  tags                = var.tags
}

resource "azurerm_linux_function_app" "this" {
  name                          = var.name
  location                      = var.location
  resource_group_name           = var.resource_group_name
  service_plan_id               = azurerm_service_plan.this.id
  storage_account_name          = azurerm_storage_account.this.name
  storage_uses_managed_identity = true
  functions_extension_version   = var.functions_extension_version
  https_only                    = var.https_only
  public_network_access_enabled = var.public_network_access_enabled
  tags                          = var.tags

  app_settings = var.app_settings

  identity {
    type = "SystemAssigned"
  }

  site_config {
    always_on = false

    application_stack {
      python_version = var.python_version
    }
  }
}

resource "azurerm_role_assignment" "storage_blob_owner" {
  scope                = azurerm_storage_account.this.id
  role_definition_name = "Storage Blob Data Owner"
  principal_id         = azurerm_linux_function_app.this.identity[0].principal_id
}
