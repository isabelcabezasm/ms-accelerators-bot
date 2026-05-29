terraform {
  required_version = ">= 1.9.0"

  required_providers {
    azapi = {
      source  = "Azure/azapi"
      version = "~> 2.4"
    }
    azuread = {
      source  = "hashicorp/azuread"
      version = "~> 3.5"
    }
    azurerm = {
      source  = "hashicorp/azurerm"
      version = "~> 4.31"
    }
  }

  backend "azurerm" {}
}

provider "azurerm" {
  features {}

  storage_use_azuread = true
}

provider "azapi" {}

data "azurerm_client_config" "current" {}

provider "azuread" {}

locals {
  name_prefix                           = lower(join("-", [var.project_name, var.environment]))
  cosmos_account_name                   = substr("${local.name_prefix}-cosmos", 0, 44)
  cosmos_database_name                  = "accelerators"
  cosmos_container_name                 = "accelerators"
  storage_account_name                  = substr("${replace(local.name_prefix, "-", "")}st", 0, 24)
  key_vault_name                        = substr("${replace(local.name_prefix, "-", "")}kv", 0, 24)
  key_vault_managed_identity_object_ids = length(var.key_vault_managed_identity_object_ids) > 0 ? var.key_vault_managed_identity_object_ids : var.managed_identity_principal_ids
  key_vault_tenant_id                   = coalesce(var.tenant_id, data.azurerm_client_config.current.tenant_id)
  compute_name_prefix                   = substr(replace(local.name_prefix, "-", ""), 0, 12)
  unique_suffix                         = substr(md5(join("-", [var.project_name, var.environment, var.location])), 0, 6)
  search_service_name                   = substr("${local.name_prefix}-search", 0, 60)
  openai_account_name                   = substr(lower(replace("${var.project_name}${var.environment}aoai", "-", "")), 0, 24)
  common_tags = merge(
    {
      environment = var.environment
      managed_by  = "terraform"
      project     = var.project_name
    },
    var.tags,
  )
  external_id_spa_redirect_uris = toset(
    compact(
      concat(
        var.environment != "prod" ? ["http://localhost:5173/"] : [],
        var.external_id_frontend_hostname == null ? [] : ["https://${var.external_id_frontend_hostname}/"],
        tolist(var.external_id_additional_spa_redirect_uris),
      )
    )
  )
}

module "resource_group" {
  source = "./modules/resource_group"

  name     = "${local.name_prefix}-rg"
  location = var.location
  tags     = local.common_tags
}

module "monitoring" {
  source = "./modules/monitoring"

  name                = local.name_prefix
  location            = var.location
  resource_group_name = module.resource_group.name
  tags                = local.common_tags
}

module "cosmos" {
  source = "./modules/cosmos"

  name                           = local.cosmos_account_name
  location                       = var.location
  resource_group_name            = module.resource_group.name
  database_name                  = local.cosmos_database_name
  container_name                 = local.cosmos_container_name
  partition_key_path             = "/userId"
  managed_identity_principal_ids = var.managed_identity_principal_ids
  tags                           = local.common_tags
}

module "search" {
  source = "./modules/search"

  name                           = local.search_service_name
  location                       = var.location
  resource_group_name            = module.resource_group.name
  managed_identity_principal_ids = tolist(var.managed_identity_principal_ids)
  tags                           = local.common_tags
}

module "storage" {
  source = "./modules/storage"

  name                           = local.storage_account_name
  location                       = var.location
  resource_group_name            = module.resource_group.name
  container_name                 = "raw-snapshots"
  managed_identity_principal_ids = var.managed_identity_principal_ids
  tags                           = local.common_tags
}

module "keyvault" {
  source = "./modules/keyvault"

  name                        = local.key_vault_name
  location                    = var.location
  resource_group_name         = module.resource_group.name
  tenant_id                   = local.key_vault_tenant_id
  managed_identity_object_ids = local.key_vault_managed_identity_object_ids
  tags                        = local.common_tags
}

module "container_app" {
  source = "./modules/container_app"

  name                = "${local.compute_name_prefix}-${var.environment}-${local.unique_suffix}-api"
  environment_name    = "${local.compute_name_prefix}-${var.environment}-${local.unique_suffix}-env"
  location            = var.location
  resource_group_name = module.resource_group.name
  tags                = local.common_tags
}

module "functions" {
  source = "./modules/functions"

  name                = "${local.compute_name_prefix}-${var.environment}-${local.unique_suffix}-func"
  location            = var.location
  resource_group_name = module.resource_group.name
  tags                = local.common_tags
}

module "swa" {
  source = "./modules/swa"

  name                = "${local.compute_name_prefix}-${var.environment}-${local.unique_suffix}-web"
  location            = var.static_web_app_location
  resource_group_name = module.resource_group.name
  tags                = local.common_tags
}

module "front_door" {
  count = var.front_door_enabled ? 1 : 0

  source = "./modules/front_door"

  name                     = "${local.name_prefix}-fd"
  resource_group_name      = module.resource_group.name
  sku_name                 = var.front_door_sku_name
  response_timeout_seconds = var.front_door_response_timeout_seconds
  endpoint_name            = var.front_door_endpoint_name
  waf_mode                 = var.front_door_waf_mode
  swa_origin               = var.front_door_swa_origin
  container_app_origin     = var.front_door_container_app_origin
  custom_domains           = var.front_door_custom_domains
  cors_allowed_origin      = var.front_door_cors_allowed_origin
  tags                     = local.common_tags
}

module "external_id" {
  source = "./modules/external_id"

  name                      = local.name_prefix
  api_identifier_uri        = var.external_id_api_identifier_uri
  frontend_hostname         = var.external_id_frontend_hostname
  owner_object_ids          = var.external_id_owner_object_ids
  sign_in_audience          = var.external_id_sign_in_audience
  spa_redirect_uris         = local.external_id_spa_redirect_uris
  social_identity_providers = var.external_id_social_identity_providers
  user_flows                = var.external_id_user_flows
  tags                      = local.common_tags
}

module "openai" {
  source = "./modules/openai"

  name                           = local.openai_account_name
  custom_subdomain_name          = local.openai_account_name
  location                       = var.location
  resource_group_name            = module.resource_group.name
  managed_identity_principal_ids = tolist(var.managed_identity_principal_ids)
  tags                           = local.common_tags
}
