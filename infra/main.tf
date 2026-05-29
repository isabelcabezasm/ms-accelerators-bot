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

locals {
  name_prefix = lower(join("-", [var.project_name, var.environment]))
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
}
