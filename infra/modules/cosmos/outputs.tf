output "account_id" {
  description = "Resource ID of the Cosmos DB account."
  value       = azurerm_cosmosdb_account.this.id
}

output "account_name" {
  description = "Name of the Cosmos DB account."
  value       = azurerm_cosmosdb_account.this.name
}

output "database_id" {
  description = "Resource ID of the Cosmos DB SQL database."
  value       = azurerm_cosmosdb_sql_database.this.id
}

output "database_name" {
  description = "Name of the Cosmos DB SQL database."
  value       = azurerm_cosmosdb_sql_database.this.name
}

output "container_id" {
  description = "Resource ID of the Cosmos DB SQL container."
  value       = azurerm_cosmosdb_sql_container.this.id
}

output "container_name" {
  description = "Name of the Cosmos DB SQL container."
  value       = azurerm_cosmosdb_sql_container.this.name
}

output "endpoint" {
  description = "Endpoint for the Cosmos DB account."
  value       = azurerm_cosmosdb_account.this.endpoint
}
