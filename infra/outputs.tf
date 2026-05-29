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

output "resource_ids" {
  description = "Key resource IDs provisioned by the current scaffold."
  value = {
    resource_group = module.resource_group.id
  }
}
