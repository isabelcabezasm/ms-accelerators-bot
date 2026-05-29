output "endpoint" {
  description = "Endpoint of the Azure AI Search service."
  value       = "https://${azurerm_search_service.this.name}.search.windows.net"
}

output "id" {
  description = "Resource ID of the Azure AI Search service."
  value       = azurerm_search_service.this.id
}

output "identity_principal_id" {
  description = "System-assigned managed identity principal ID for the search service."
  value       = azurerm_search_service.this.identity[0].principal_id
}

output "managed_identity_role_assignment_ids" {
  description = "Role assignment IDs granting managed identities Search Index Data Reader."
  value       = { for principal_id, assignment in azurerm_role_assignment.index_data_reader : principal_id => assignment.id }
}

output "name" {
  description = "Name of the Azure AI Search service."
  value       = azurerm_search_service.this.name
}

output "placeholder_index_id" {
  description = "Identifier of the placeholder hybrid index."
  value       = azapi_data_plane_resource.placeholder_index.id
}

output "placeholder_index_name" {
  description = "Name of the placeholder hybrid index."
  value       = azapi_data_plane_resource.placeholder_index.name
}
