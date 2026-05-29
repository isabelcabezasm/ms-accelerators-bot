resource "azurerm_static_web_app" "this" {
  name                = var.name
  location            = var.location
  resource_group_name = var.resource_group_name
  sku_tier            = var.sku_tier
  sku_size            = var.sku_size
  tags                = var.tags

  app_settings = var.app_settings

  identity {
    type = "SystemAssigned"
  }
}
