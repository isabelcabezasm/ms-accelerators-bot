# Project Context

- **Owner:** Isabel Cabezas
- **Project:** Microsoft Accelerators Finder — AI assistant for discovering Microsoft Accelerators using RAG (Azure AI Search + Azure OpenAI), FastAPI backend, React+Vite frontend, Entra External ID auth, Terraform IaC.
- **Stack:** Python 3.12, FastAPI, Azure AI Search, Azure OpenAI, React, Vite, TypeScript, Fluent UI, MSAL.js, Terraform, Azure Container Apps, Azure Functions, Cosmos DB, Azure Front Door + WAF
- **Created:** 2026-05-29

## Learnings

<!-- Append new learnings below. Each entry is something lasting about the project. -->

### 2026-05-29 — Phase 0 Batch 1 PRs Ready for Code Review

**PR #35 (Joey):** Repository directory structure scaffolding. Tests and lint pass. Ready for review.
**PR #36 (Gunther):** Terraform stack with providers, remote state backend, resource group module, and stubs. terraform validate passes. Ready for review.

Per Isabel's directive (2026-05-29): Review these PRs, add comments, and approve if acceptable. Coordinate with Chandler (security) on PR #36 infrastructure changes.

### 2026-05-29T11:54:49.343+00:00 — Review findings from PRs #35 and #36

- Phase 0 scaffold reviews need to check the full contract in `docs/proposal.md`, not just top-level folders. PR #35 created `src/shared/`, but the agreed shared surface also includes prompts and auth placeholders.
- For infrastructure scaffolds, `terraform init -backend=false` plus `terraform validate` is not enough to satisfy the team's acceptance bar. PR #36 still needs reproducible evidence that the real remote-backend `terraform init` and `terraform plan` path works before merge.
- Positive pattern: the backend/frontend scaffold in PR #35 is already wired cleanly enough to pass editable install, lint, typing, tests, and frontend build checks, so the remaining gap is structural completeness rather than code quality.

### 2026-05-29T12:50:38Z — Phase 0 Batch 2 Code Review Complete

**Code Review of 7 Phase 0 PRs (#37–#43):**
- 3 blocking issues identified across the PRs:
  1. PR #38 (Cosmos DB): RBAC incorrectly used generic role assignment instead of `azurerm_cosmosdb_sql_role_assignment`
  2. PR #40 (Functions): Hardcoded storage access keys instead of managed identity
  3. PR #41 (Front Door): Rate limit rules not specifically targeting `/chat/` prefix

**Resolution:**
- All 3 blocking issues flagged to gunther-fixes-batch2
- Gunther corrected all issues; PRs re-approved and merged
- Code quality remains high; issues were infrastructure-specific design decisions

**Architecture Patterns Validated:**
- Managed identities properly configured across services
- Terraform RBAC patterns correct for Cosmos DB
- Rate limiting rules properly scoped to target endpoint
- Phase 0 code quality and security gate maintained
