output "id" {
  description = "Resource ID of the Function App."
  value       = azurerm_linux_function_app.this.id
}

output "name" {
  description = "Name of the Function App."
  value       = azurerm_linux_function_app.this.name
}

output "plan_id" {
  description = "Resource ID of the consumption App Service plan."
  value       = azurerm_service_plan.this.id
}

output "principal_id" {
  description = "Principal ID of the Function App managed identity."
  value       = azurerm_linux_function_app.this.identity[0].principal_id
}

output "storage_account_id" {
  description = "Resource ID of the Function App storage account."
  value       = azurerm_storage_account.this.id
}

output "storage_account_name" {
  description = "Name of the Function App storage account."
  value       = azurerm_storage_account.this.name
}

output "url" {
  description = "HTTPS URL for the Function App."
  value       = format("https://%s", azurerm_linux_function_app.this.default_hostname)
}
