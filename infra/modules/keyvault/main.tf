resource "azurerm_key_vault" "this" {
  name                       = var.name
  location                   = var.location
  resource_group_name        = var.resource_group_name
  tenant_id                  = var.tenant_id
  sku_name                   = "standard"
  soft_delete_retention_days = 90
  purge_protection_enabled   = true
  tags                       = var.tags
}

resource "azurerm_key_vault_access_policy" "managed_identity" {
  for_each = var.managed_identity_object_ids

  key_vault_id = azurerm_key_vault.this.id
  tenant_id    = var.tenant_id
  object_id    = each.value

  key_permissions = [
    "Get",
    "List",
  ]

  secret_permissions = [
    "Get",
    "List",
  ]
}
