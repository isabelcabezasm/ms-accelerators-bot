output "deployment_ids" {
  description = "Resource IDs for the Azure OpenAI model deployments."
  value       = { for name, deployment in azapi_resource.deployment : name => deployment.id }
}

output "deployment_names" {
  description = "Deployment names keyed by logical purpose."
  value       = { for name, deployment in azapi_resource.deployment : name => deployment.name }
}

output "embedding_dimensions" {
  description = "Embedding vector dimension exposed by the embeddings deployment."
  value       = var.embedding_dimensions
}

output "endpoint" {
  description = "Endpoint of the Azure OpenAI account."
  value       = azurerm_cognitive_account.this.endpoint
}

output "id" {
  description = "Resource ID of the Azure OpenAI account."
  value       = azurerm_cognitive_account.this.id
}

output "identity_principal_id" {
  description = "System-assigned managed identity principal ID for the Azure OpenAI account."
  value       = azurerm_cognitive_account.this.identity[0].principal_id
}

output "managed_identity_role_assignment_ids" {
  description = "Role assignment IDs granting managed identities Cognitive Services OpenAI User."
  value       = { for principal_id, assignment in azurerm_role_assignment.openai_user : principal_id => assignment.id }
}

output "name" {
  description = "Name of the Azure OpenAI account."
  value       = azurerm_cognitive_account.this.name
}
