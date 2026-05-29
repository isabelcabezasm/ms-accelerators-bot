# Project Context

- **Owner:** Isabel Cabezas
- **Project:** Microsoft Accelerators Finder — AI assistant for discovering Microsoft Accelerators using RAG (Azure AI Search + Azure OpenAI), FastAPI backend, React+Vite frontend, Entra External ID auth, Terraform IaC.
- **Stack:** Python 3.12, FastAPI, Azure AI Search, Azure OpenAI, React, Vite, TypeScript, Fluent UI, MSAL.js, Terraform, Azure Container Apps, Azure Functions, Cosmos DB, Azure Front Door + WAF
- **Created:** 2026-05-29

## Learnings

<!-- Append new learnings below. Each entry is something lasting about the project. -->

### 2026-05-29 — PRD Decomposed into 33 GitHub Issues

Monica (Lead) created 33 issues (#1–#33) across 6 phases from `docs/proposal.md`. **Your assignments:** Infrastructure lead (#1–#7, #25, #29) — Terraform stack, AI Search, Cosmos DB, Container Apps, Front Door + WAF, App Insights. See decisions.md for full details and squad assignments. **Blocked:** Project board linking needs Isabel to refresh token scope (`gh auth refresh -s read:project`).

### 2026-05-29T11:54:49.343+00:00 — Terraform Phase 0 scaffold baseline

- Added the Terraform root at `infra/` with AzureRM and AzAPI providers plus a partial Azure Storage backend (`backend "azurerm" {}`) so environment-specific backend values stay outside source control.
- Implemented the first real module at `infra/modules/resource_group/` and standardized placeholder module triplets (`main.tf`, `variables.tf`, `outputs.tf`) for `search`, `openai`, `container_app`, `functions`, `swa`, `cosmos`, `front_door`, `external_id`, `keyvault`, and `monitoring`.
- Captured backend bootstrap guidance in `infra/backend.hcl.example` and `infra/README.md`; `.gitignore` now excludes Terraform working directories, plans, and state files.
**Phase 0 Batch 1 Completion (2026-05-29T11:54:49Z):** Issue #1 (Terraform stack scaffold) completed. PR #36 opened with providers, remote state backend, resource group module, and module stubs. terraform validate passes. Infrastructure foundation ready for Phase 0 service work (#2–#7).

### 2026-05-29T12:50:38Z — Phase 0 Batch 2 Implementation Complete

**Issues Completed:**
- Issue #2: AI Search + OpenAI → PR #43 merged
- Issue #3: Cosmos DB + Blob Storage + Key Vault → PR #38 merged
- Issue #4: Container Apps + Functions + Static Web Apps → PR #40 merged
- Issue #5: Front Door + Web Application Firewall → PR #41 merged
- Issue #7: App Insights + Log Analytics → PR #37 merged
- Issue #34: CI/CD Pipeline with GitHub Actions → PR #39 merged

**Key Technical Decisions:**
- Cosmos DB RBAC uses `azurerm_cosmosdb_sql_role_assignment` (not generic role assignment)
- Functions use managed identity for storage access (no access keys)
- Front Door rate limiting targets `/chat/` prefix specifically
- GitHub Actions workflows pinned to commit SHAs for supply chain security
- OpenAI models pinned: gpt-4o-mini:2024-07-18, text-embedding-3-large:1
- Key Vault with purge protection enabled and 90-day retention

**Review & Fixes:**
- Ross code review identified 3 blocking issues (RBAC, managed identity, rate limits) — all resolved
- Gunther applied fixes across 6 PRs; all re-approved and merged
- Phase 0 complete: 7 service PRs + 1 pipeline PR = 8 total Phase 0 deliverables merged
