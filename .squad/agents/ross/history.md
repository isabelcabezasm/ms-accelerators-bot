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
