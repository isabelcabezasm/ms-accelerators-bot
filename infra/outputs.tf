output "container_app_principal_id" {
  description = "Principal ID of the Container App managed identity."
  value       = module.container_app.principal_id
}

output "container_app_url" {
  description = "URL of the Container App ingress endpoint."
  value       = module.container_app.url
}

output "function_app_principal_id" {
  description = "Principal ID of the Function App managed identity."
  value       = module.functions.principal_id
}

output "function_app_url" {
  description = "URL of the Function App."
  value       = module.functions.url
}

output "managed_identity_principal_ids" {
  description = "Managed identity principal IDs for the compute resources."
  value = {
    container_app  = module.container_app.principal_id
    function_app   = module.functions.principal_id
    static_web_app = module.swa.principal_id
  }
}

output "name_prefix" {
  description = "Naming prefix shared by Terraform-managed resources."
  value       = local.name_prefix
}

output "openai_deployment_names" {
  description = "Azure OpenAI deployment names keyed by logical purpose."
  value       = module.openai.deployment_names
}

output "openai_endpoint" {
  description = "Endpoint of the Azure OpenAI account."
  value       = module.openai.endpoint
}

output "openai_id" {
  description = "Resource ID of the Azure OpenAI account."
  value       = module.openai.id
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

output "front_door_profile_id" {
  description = "Resource ID of the Front Door profile when enabled."
  value       = try(module.front_door[0].profile_id, null)
}

output "front_door_endpoint_host_name" {
  description = "Front Door endpoint host name when enabled."
  value       = try(module.front_door[0].endpoint_host_name, null)

output "external_id" {
  description = "Entra External ID client IDs, tenant info, and manual configuration placeholders."
  value = {
    tenant_id            = module.external_id.tenant_id
    api_client_id        = module.external_id.api.client_id
    api_identifier_uri   = module.external_id.api.identifier_uri
    spa_client_id        = module.external_id.spa.client_id
    manual_configuration = module.external_id.manual_configuration
  }
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

    container_app  = module.container_app.id
    function_app   = module.functions.id
    resource_group = module.resource_group.id
    static_web_app = module.swa.id
  }
}

output "static_web_app_principal_id" {
  description = "Principal ID of the Static Web App managed identity."
  value       = module.swa.principal_id
}

output "static_web_app_url" {
  description = "URL of the Static Web App."
  value       = module.swa.url
}

output "workload_urls" {
  description = "Public URLs for the compute workloads."
  value = {
    container_app  = module.container_app.url
    function_app   = module.functions.url
    static_web_app = module.swa.url

    front_door     = try(module.front_door[0].profile_id, null)

    resource_group                    = module.resource_group.id
    external_id_api_application       = module.external_id.api.id
    external_id_spa_application       = module.external_id.spa.id
    external_id_api_service_principal = module.external_id.api.service_principal_id
    external_id_spa_service_principal = module.external_id.spa.service_principal_id

    openai         = module.openai.id
    openai_models  = module.openai.deployment_ids
    resource_group = module.resource_group.id
    search         = module.search.id
    search_index   = module.search.placeholder_index_id
  }
}

output "search_endpoint" {
  description = "Endpoint of the Azure AI Search service."
  value       = module.search.endpoint
}

output "search_id" {
  description = "Resource ID of the Azure AI Search service."
  value       = module.search.id
}

output "search_index_name" {
  description = "Name of the placeholder hybrid search index."
  value       = module.search.placeholder_index_name
}
