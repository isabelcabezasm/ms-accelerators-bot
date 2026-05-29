output "account_id" {
  description = "Resource ID of the storage account."
  value       = azurerm_storage_account.this.id
}

output "account_name" {
  description = "Name of the storage account."
  value       = azurerm_storage_account.this.name
}

output "container_id" {
  description = "Resource ID of the blob container."
  value       = azurerm_storage_container.this.id
}

output "container_name" {
  description = "Name of the blob container."
  value       = azurerm_storage_container.this.name
}

output "primary_blob_endpoint" {
  description = "Primary blob endpoint of the storage account."
  value       = azurerm_storage_account.this.primary_blob_endpoint
}
