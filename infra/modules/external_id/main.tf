terraform {
  required_providers {
    azuread = {
      source  = "hashicorp/azuread"
      version = "~> 3.5"
    }
  }
}

data "azuread_client_config" "current" {}

locals {
  owner_object_ids = toset(
    concat(tolist(var.owner_object_ids), [data.azuread_client_config.current.object_id])
  )
  spa_redirect_uris = length(var.spa_redirect_uris) > 0 ? var.spa_redirect_uris : toset(
    compact([
      "http://localhost:5173",
      var.frontend_hostname == null ? null : "https://${var.frontend_hostname}",
    ])
  )
  api_identifier_uri = coalesce(var.api_identifier_uri, "api://${var.name}-api")
  app_role_ids = {
    user  = "ce1273d1-9ee4-44ae-884f-eb366a3b0702"
    admin = "97969ff9-1d24-4377-83da-776f37c5bcbe"
  }
  api_scope_ids = {
    access_as_user = "3ecca70d-8a9b-4343-989c-3ca9053685f8"
  }
}

resource "azuread_application" "api" {
  display_name     = "${var.name}-api"
  identifier_uris  = [local.api_identifier_uri]
  owners           = local.owner_object_ids
  sign_in_audience = var.sign_in_audience

  api {
    requested_access_token_version = 2

    oauth2_permission_scope {
      admin_consent_description  = "Allow the SPA to call the Accelerator Finder API on behalf of the signed-in user."
      admin_consent_display_name = "Access Accelerator Finder API"
      enabled                    = true
      id                         = local.api_scope_ids.access_as_user
      type                       = "User"
      user_consent_description   = "Allow the application to access Accelerator Finder on your behalf."
      user_consent_display_name  = "Access Accelerator Finder"
      value                      = "access_as_user"
    }
  }

  app_role {
    allowed_member_types = ["User"]
    description          = "Baseline role for signed-in customers of Accelerator Finder."
    display_name         = "User"
    enabled              = true
    id                   = local.app_role_ids.user
    value                = "user"
  }

  app_role {
    allowed_member_types = ["User"]
    description          = "Administrative role for support, ingestion, and operational actions."
    display_name         = "Admin"
    enabled              = true
    id                   = local.app_role_ids.admin
    value                = "admin"
  }
}

resource "azuread_service_principal" "api" {
  app_role_assignment_required = false
  client_id                    = azuread_application.api.client_id
  owners                       = local.owner_object_ids
}

resource "azuread_application" "spa" {
  display_name     = "${var.name}-spa"
  owners           = local.owner_object_ids
  sign_in_audience = var.sign_in_audience

  required_resource_access {
    resource_app_id = azuread_application.api.client_id

    resource_access {
      id   = local.api_scope_ids.access_as_user
      type = "Scope"
    }
  }

  single_page_application {
    redirect_uris = sort(tolist(local.spa_redirect_uris))
  }
}

resource "azuread_service_principal" "spa" {
  app_role_assignment_required = false
  client_id                    = azuread_application.spa.client_id
  owners                       = local.owner_object_ids
}
