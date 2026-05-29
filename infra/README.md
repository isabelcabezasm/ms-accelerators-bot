# Terraform scaffold

This directory contains the Phase 0 Terraform root and module stubs.

## Remote state

Before `terraform init` can use the AzureRM backend, bootstrap the remote state
resources and sign in to Azure with an identity that can read and write them:

1. Create the backend resource group.
2. Create the backend storage account.
3. Create the blob container that will hold the Terraform state.
4. Copy `backend.hcl.example` to a real backend config file (for example,
   `backend.dev.hcl`) and fill in those resource names.
5. Authenticate with Azure (`az login` or equivalent workload identity/service
   principal) and make sure that identity has data-plane access to the state
   container plus subscription access for `terraform plan`.

The real remote-backend flow is:

```bash
cp infra/backend.hcl.example infra/backend.dev.hcl
terraform -chdir=infra init -backend-config=backend.dev.hcl
terraform -chdir=infra plan
```

If the storage account, container, or Azure credentials are missing, `init`
against the remote backend will fail. In that case, use the local validation
commands below until the backend bootstrap is complete.

## Local validation

When backend values are not available yet, validate providers and modules with:

```bash
terraform -chdir=infra init -backend=false
terraform -chdir=infra validate
```
