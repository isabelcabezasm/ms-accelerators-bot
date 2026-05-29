terraform {
  required_version = ">= 1.9.0"

  required_providers {
    azapi = {
      source  = "Azure/azapi"
      version = "~> 2.4"
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
}

provider "azapi" {}

data "azurerm_client_config" "current" {}

locals {
  name_prefix                           = lower(join("-", [var.project_name, var.environment]))
  cosmos_account_name                   = substr("${local.name_prefix}-cosmos", 0, 44)
  cosmos_database_name                  = "accelerators"
  cosmos_container_name                 = "accelerators"
  storage_account_name                  = substr("${replace(local.name_prefix, "-", "")}st", 0, 24)
  key_vault_name                        = substr("${replace(local.name_prefix, "-", "")}kv", 0, 24)
  key_vault_managed_identity_object_ids = length(var.key_vault_managed_identity_object_ids) > 0 ? var.key_vault_managed_identity_object_ids : var.managed_identity_principal_ids
  key_vault_tenant_id                   = coalesce(var.tenant_id, data.azurerm_client_config.current.tenant_id)

  name_prefix         = lower(join("-", [var.project_name, var.environment]))
  compute_name_prefix = substr(replace(local.name_prefix, "-", ""), 0, 12)
  unique_suffix       = substr(md5(join("-", [var.project_name, var.environment, var.location])), 0, 6)
  common_tags = merge(
    {
      environment = var.environment
      managed_by  = "terraform"
      project     = var.project_name
    },
    var.tags,
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
  location            = var.location
  resource_group_name = module.resource_group.name
  tags                = local.common_tags
}
