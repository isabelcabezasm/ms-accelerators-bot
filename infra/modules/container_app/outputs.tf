output "environment_id" {
  description = "Resource ID of the Container Apps environment."
  value       = azurerm_container_app_environment.this.id
}

output "environment_name" {
  description = "Name of the Container Apps environment."
  value       = azurerm_container_app_environment.this.name
}

output "environment_principal_id" {
  description = "Principal ID of the Container Apps environment managed identity when available."
  value       = try(azurerm_container_app_environment.this.identity[0].principal_id, null)
}

output "id" {
  description = "Resource ID of the Container App."
  value       = azurerm_container_app.this.id
}

output "latest_revision_fqdn" {
  description = "FQDN of the latest Container App revision."
  value       = azurerm_container_app.this.latest_revision_fqdn
}

output "name" {
  description = "Name of the Container App."
  value       = azurerm_container_app.this.name
}

output "principal_id" {
  description = "Principal ID of the Container App managed identity."
  value       = azurerm_container_app.this.identity[0].principal_id
}

output "url" {
  description = "HTTPS URL for the Container App ingress endpoint."
  value       = try(format("https://%s", azurerm_container_app.this.latest_revision_fqdn), null)
}
