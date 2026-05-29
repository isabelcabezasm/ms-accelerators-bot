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

output "application_insights_connection_string" {
  description = "Application Insights connection string shared by all workloads."
  value       = module.monitoring.application_insights_connection_string
  sensitive   = true
}

output "application_insights_id" {
  description = "Resource ID of the shared Application Insights instance."
  value       = module.monitoring.id
}

output "log_analytics_workspace_id" {
  description = "Resource ID of the shared Log Analytics workspace."
  value       = module.monitoring.log_analytics_workspace_id

output "cosmos_account_id" {
  description = "Resource ID of the Cosmos DB account."
  value       = module.cosmos.account_id
}

output "storage_account_id" {
  description = "Resource ID of the storage account."
  value       = module.storage.account_id
}

output "key_vault_id" {
  description = "Resource ID of the Key Vault."
  value       = module.keyvault.id
}

output "resource_ids" {
  description = "Key resource IDs provisioned by the current scaffold."
  value = {
    app_insights   = module.monitoring.id
    log_analytics  = module.monitoring.log_analytics_workspace_id
    resource_group = module.resource_group.id

    cosmos_account    = module.cosmos.account_id
    cosmos_container  = module.cosmos.container_id
    key_vault         = module.keyvault.id
    resource_group    = module.resource_group.id
    storage_account   = module.storage.account_id
    storage_container = module.storage.container_id
  }
}
