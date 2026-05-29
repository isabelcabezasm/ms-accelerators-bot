resource "azurerm_storage_account" "this" {
  name                     = var.name
  resource_group_name      = var.resource_group_name
  location                 = var.location
  account_tier             = "Standard"
  account_replication_type = "LRS"
  account_kind             = "StorageV2"
  min_tls_version          = "TLS1_2"

  allow_nested_items_to_be_public = false
  shared_access_key_enabled       = false
  tags                            = var.tags
}

resource "azurerm_storage_container" "this" {
  name                  = var.container_name
  storage_account_id    = azurerm_storage_account.this.id
  container_access_type = "private"
}

resource "azurerm_role_assignment" "blob_contributor" {
  for_each = var.managed_identity_principal_ids

  scope                = azurerm_storage_account.this.id
  role_definition_name = "Storage Blob Data Contributor"
  principal_id         = each.value
}
