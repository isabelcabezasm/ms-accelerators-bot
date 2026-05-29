terraform {
  required_providers {
    azapi = {
      source = "Azure/azapi"
    }
    azurerm = {
      source = "hashicorp/azurerm"
    }
  }
}

locals {
  custom_subdomain_name = coalesce(var.custom_subdomain_name, var.name)
  deployments = {
    chat = {
      name          = var.chat_deployment_name
      model_name    = var.chat_model_name
      model_version = var.chat_model_version
      capacity      = var.chat_deployment_capacity
    }
    embeddings = {
      name          = var.embedding_deployment_name
      model_name    = var.embedding_model_name
      model_version = var.embedding_model_version
      capacity      = var.embedding_deployment_capacity
    }
  }
}

resource "azurerm_cognitive_account" "this" {
  name                          = var.name
  location                      = var.location
  resource_group_name           = var.resource_group_name
  kind                          = "OpenAI"
  sku_name                      = var.sku_name
  custom_subdomain_name         = local.custom_subdomain_name
  public_network_access_enabled = var.public_network_access_enabled
  local_auth_enabled            = var.local_auth_enabled
  tags                          = var.tags

  identity {
    type = "SystemAssigned"
  }
}

resource "azapi_resource" "deployment" {
  for_each = local.deployments

  type      = "Microsoft.CognitiveServices/accounts/deployments@2024-10-01"
  name      = each.value.name
  parent_id = azurerm_cognitive_account.this.id
  tags      = var.tags

  body = {
    properties = {
      model = {
        format  = "OpenAI"
        name    = each.value.model_name
        version = each.value.model_version
      }
      versionUpgradeOption = "OnceNewDefaultVersionAvailable"
    }
    sku = {
      name     = var.deployment_sku_name
      capacity = each.value.capacity
    }
  }

  schema_validation_enabled = false
}

resource "azurerm_role_assignment" "openai_user" {
  for_each = toset(var.managed_identity_principal_ids)

  scope                = azurerm_cognitive_account.this.id
  role_definition_name = "Cognitive Services OpenAI User"
  principal_id         = each.value
  principal_type       = "ServicePrincipal"
}
