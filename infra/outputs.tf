output "name_prefix" {
  description = "Naming prefix shared by Terraform-managed resources."
  value       = local.name_prefix
}

output "resource_group_id" {
  description = "Resource ID of the shared resource group."
  value       = module.resource_group.id
}

output "resource_group_name" {
  description = "Name of the shared resource group."
  value       = module.resource_group.name
}

output "application_insights_connection_string_api" {
  description = "Application Insights connection string for the API workload."
  value       = module.monitoring.api_connection_string
  sensitive   = true
}

output "application_insights_connection_string_functions" {
  description = "Application Insights connection string for the Functions workload."
  value       = module.monitoring.functions_connection_string
  sensitive   = true
}

output "application_insights_id" {
  description = "Resource ID of the shared Application Insights instance."
  value       = module.monitoring.id
}

output "log_analytics_workspace_id" {
  description = "Resource ID of the shared Log Analytics workspace."
  value       = module.monitoring.log_analytics_workspace_id
}

output "resource_ids" {
  description = "Key resource IDs provisioned by the current scaffold."
  value = {
    app_insights   = module.monitoring.id
    log_analytics  = module.monitoring.log_analytics_workspace_id
    resource_group = module.resource_group.id
  }
}
