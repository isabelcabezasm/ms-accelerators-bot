# Terraform scaffold

This directory contains the Phase 0 Terraform root and module stubs.

## Remote state

Copy `backend.hcl.example` to a real backend configuration file and supply the
Azure Storage values for the target environment, then initialize Terraform:

```bash
terraform -chdir=infra init -backend-config=backend.hcl
```

## Local validation

When backend values are not available yet, validate providers and modules with:

```bash
terraform -chdir=infra init -backend=false
terraform -chdir=infra validate
```
