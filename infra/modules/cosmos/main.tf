resource "azurerm_cosmosdb_account" "this" {
  name                = var.name
  location            = var.location
  resource_group_name = var.resource_group_name
  offer_type          = "Standard"
  kind                = "GlobalDocumentDB"

  capabilities {
    name = "EnableServerless"
  }

  consistency_policy {
    consistency_level = "Session"
  }

  geo_location {
    location          = var.location
    failover_priority = 0
    zone_redundant    = false
  }

  local_authentication_disabled = true
  tags                          = var.tags
}

resource "azurerm_cosmosdb_sql_database" "this" {
  name                = var.database_name
  resource_group_name = var.resource_group_name
  account_name        = azurerm_cosmosdb_account.this.name
}

resource "azurerm_cosmosdb_sql_container" "this" {
  name                  = var.container_name
  resource_group_name   = var.resource_group_name
  account_name          = azurerm_cosmosdb_account.this.name
  database_name         = azurerm_cosmosdb_sql_database.this.name
  partition_key_paths   = [var.partition_key_path]
  partition_key_kind    = "Hash"
  partition_key_version = 2
}

resource "azurerm_cosmosdb_sql_role_assignment" "data_contributor" {
  for_each = var.managed_identity_principal_ids

  resource_group_name = var.resource_group_name
  account_name        = azurerm_cosmosdb_account.this.name
  # Built-in "Cosmos DB Built-in Data Contributor" role definition ID
  role_definition_id = "${azurerm_cosmosdb_account.this.id}/sqlRoleDefinitions/00000000-0000-0000-0000-000000000002"
  principal_id       = each.value
  scope              = azurerm_cosmosdb_account.this.id
}
