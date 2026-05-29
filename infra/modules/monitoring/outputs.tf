output "id" {
  description = "Resource ID of the Application Insights instance."
  value       = azurerm_application_insights.this.id
}

output "name" {
  description = "Name of the Application Insights instance."
  value       = azurerm_application_insights.this.name
}

output "application_insights_connection_string" {
  description = "Application Insights connection string shared by all workloads."
  value       = azurerm_application_insights.this.connection_string
  sensitive   = true
}

output "instrumentation_key" {
  description = "Instrumentation key retained for compatibility with older Azure SDKs."
  value       = azurerm_application_insights.this.instrumentation_key
  sensitive   = true
}

output "log_analytics_workspace_id" {
  description = "Resource ID of the Log Analytics workspace."
  value       = azurerm_log_analytics_workspace.this.id
}

output "log_analytics_workspace_name" {
  description = "Name of the Log Analytics workspace."
  value       = azurerm_log_analytics_workspace.this.name
}

output "sampling_percentage" {
  description = "Application Insights telemetry sampling percentage."
  value       = var.sampling_percentage
}
