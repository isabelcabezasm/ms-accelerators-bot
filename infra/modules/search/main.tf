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

resource "azurerm_search_service" "this" {
  name                          = var.name
  location                      = var.location
  resource_group_name           = var.resource_group_name
  sku                           = var.sku
  replica_count                 = var.replica_count
  partition_count               = var.partition_count
  semantic_search_sku           = var.semantic_search_sku
  public_network_access_enabled = var.public_network_access_enabled
  local_authentication_enabled  = var.local_authentication_enabled
  authentication_failure_mode   = var.local_authentication_enabled ? var.authentication_failure_mode : null
  tags                          = var.tags

  identity {
    type = "SystemAssigned"
  }
}

resource "azurerm_role_assignment" "index_data_reader" {
  for_each = toset(var.managed_identity_principal_ids)

  scope                = azurerm_search_service.this.id
  role_definition_name = "Search Index Data Reader"
  principal_id         = each.value
  principal_type       = "ServicePrincipal"
}

resource "azapi_data_plane_resource" "placeholder_index" {
  type      = "Microsoft.Search/searchServices/indexes@2024-07-01"
  parent_id = "${azurerm_search_service.this.name}.search.windows.net"
  name      = var.index_name

  body = {
    fields = [
      {
        name       = "id"
        type       = "Edm.String"
        key        = true
        filterable = true
        sortable   = true
        analyzer   = "keyword"
      },
      {
        name        = "parent_id"
        type        = "Edm.String"
        filterable  = true
        sortable    = true
        retrievable = true
      },
      {
        name        = "chunk_id"
        type        = "Edm.String"
        filterable  = true
        sortable    = true
        retrievable = true
      },
      {
        name        = "name"
        type        = "Edm.String"
        searchable  = true
        retrievable = true
        sortable    = true
      },
      {
        name        = "summary"
        type        = "Edm.String"
        searchable  = true
        retrievable = true
      },
      {
        name        = "long_description"
        type        = "Edm.String"
        searchable  = true
        retrievable = true
        analyzer    = "en.microsoft"
      },
      {
        name        = "categories"
        type        = "Collection(Edm.String)"
        searchable  = true
        retrievable = true
        filterable  = true
        facetable   = true
      },
      {
        name        = "industries"
        type        = "Collection(Edm.String)"
        searchable  = true
        retrievable = true
        filterable  = true
        facetable   = true
      },
      {
        name        = "azure_services"
        type        = "Collection(Edm.String)"
        searchable  = true
        retrievable = true
        filterable  = true
        facetable   = true
      },
      {
        name        = "languages"
        type        = "Collection(Edm.String)"
        searchable  = true
        retrievable = true
        filterable  = true
        facetable   = true
      },
      {
        name        = "deployment"
        type        = "Collection(Edm.String)"
        searchable  = true
        retrievable = true
        filterable  = true
        facetable   = true
      },
      {
        name        = "url"
        type        = "Edm.String"
        retrievable = true
      },
      {
        name        = "github_url"
        type        = "Edm.String"
        retrievable = true
      },
      {
        name        = "last_updated"
        type        = "Edm.DateTimeOffset"
        retrievable = true
        filterable  = true
        sortable    = true
      },
      {
        name        = "stars"
        type        = "Edm.Int32"
        retrievable = true
        filterable  = true
        sortable    = true
      },
      {
        name                = "content_vector"
        type                = "Collection(Edm.Single)"
        searchable          = true
        retrievable         = false
        stored              = false
        dimensions          = var.embedding_dimensions
        vectorSearchProfile = "default-vector-profile"
      }
    ]

    vectorSearch = {
      algorithms = [
        {
          name = "default-hnsw"
          kind = "hnsw"
          hnswParameters = {
            m              = 4
            efConstruction = 400
            efSearch       = 100
            metric         = "cosine"
          }
        }
      ]
      profiles = [
        {
          name      = "default-vector-profile"
          algorithm = "default-hnsw"
        }
      ]
    }

    semantic = {
      configurations = [
        {
          name = var.semantic_configuration_name
          prioritizedFields = {
            titleField                = { fieldName = "name" }
            prioritizedContentFields  = [{ fieldName = "long_description" }, { fieldName = "summary" }]
            prioritizedKeywordsFields = [{ fieldName = "categories" }, { fieldName = "azure_services" }]
          }
        }
      ]
    }
  }

  depends_on = [
    azurerm_search_service.this,
    azurerm_role_assignment.index_data_reader,
  ]
}
