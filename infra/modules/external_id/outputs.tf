output "name" {
  description = "Logical module name prefix used for the Entra app registrations."
  value       = var.name
}

output "tenant_id" {
  description = "Tenant ID where the module will create the Entra app registrations."
  value       = data.azuread_client_config.current.tenant_id
}

output "api" {
  description = "API app registration details, exposed scopes, and app roles."
  value = {
    id                   = azuread_application.api.id
    client_id            = azuread_application.api.client_id
    object_id            = azuread_application.api.object_id
    service_principal_id = azuread_service_principal.api.object_id
    identifier_uri       = local.api_identifier_uri
    scopes = {
      access_as_user = {
        id    = local.api_scope_ids.access_as_user
        value = "access_as_user"
      }
    }
    app_roles = {
      default = "user"
      user = {
        id    = local.app_role_ids.user
        value = "user"
      }
      admin = {
        id    = local.app_role_ids.admin
        value = "admin"
      }
    }
  }
}

output "spa" {
  description = "SPA app registration details and redirect URIs."
  value = {
    id                   = azuread_application.spa.id
    client_id            = azuread_application.spa.client_id
    object_id            = azuread_application.spa.object_id
    service_principal_id = azuread_service_principal.spa.object_id
    redirect_uris        = sort(tolist(local.spa_redirect_uris))
  }
}

output "manual_configuration" {
  description = "Manual External ID configuration that still needs to be applied in the Entra admin center."
  value = {
    social_identity_providers = var.social_identity_providers
    user_flows                = var.user_flows
    default_app_role          = "user"
  }
}
