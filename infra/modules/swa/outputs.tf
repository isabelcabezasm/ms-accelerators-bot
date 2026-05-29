output "default_host_name" {
  description = "Default hostname of the Static Web App."
  value       = azurerm_static_web_app.this.default_host_name
}

output "id" {
  description = "Resource ID of the Static Web App."
  value       = azurerm_static_web_app.this.id
}

output "name" {
  description = "Name of the Static Web App."
  value       = azurerm_static_web_app.this.name
}

output "principal_id" {
  description = "Principal ID of the Static Web App managed identity."
  value       = azurerm_static_web_app.this.identity[0].principal_id
}

output "url" {
  description = "HTTPS URL for the Static Web App."
  value       = format("https://%s", azurerm_static_web_app.this.default_host_name)
}
