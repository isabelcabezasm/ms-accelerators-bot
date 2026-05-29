# Project Context

- **Owner:** Isabel Cabezas
- **Project:** Microsoft Accelerators Finder — AI assistant for discovering Microsoft Accelerators using RAG (Azure AI Search + Azure OpenAI), FastAPI backend, React+Vite frontend, Entra External ID auth, Terraform IaC.
- **Stack:** Python 3.12, FastAPI, Azure AI Search, Azure OpenAI, React, Vite, TypeScript, Fluent UI, MSAL.js, Terraform, Azure Container Apps, Azure Functions, Cosmos DB, Azure Front Door + WAF
- **Created:** 2026-05-29

## Learnings

<!-- Append new learnings below. Each entry is something lasting about the project. -->

### 2026-05-29 — PRD Decomposed into 33 GitHub Issues

Monica (Lead) created 33 issues (#1–#33) across 6 phases from `docs/proposal.md`. **Your assignments:** Security domain (#5, #6, #13, #16, #17, #24) — Front Door + WAF, Entra External ID, JWT validation, per-user quotas, GDPR endpoints, custom domain. See decisions.md for full details and squad assignments. **Blocked:** Project board linking needs Isabel to refresh token scope (`gh auth refresh -s read:project`).

### 2026-05-29T11:54:49.343+00:00 — Security review of scaffold PRs #35 and #36

Reviewed the repo and Terraform scaffolds with a security-first lens. No hardcoded credentials, plaintext secrets, permissive CORS, or PII-leaking logs were introduced, and the Terraform remote state example correctly prefers Azure AD auth.

Blocking recommendations recorded on the PRs: ignore environment-specific local config files (`.env.local`, `.env.*`) for the app scaffold, and ignore Terraform local secret-bearing files (`*.tfvars`, `*.tfvars.json`, `backend.hcl`, `backend.*.hcl`) before more contributors start using the scaffold. These are low-effort guardrails that prevent accidental secret commits early in the project.

### 2026-05-29 — Phase 0 Batch 1: Security Review Tasks

**Issue #34 (Monica):** CI/CD pipeline architecture decision finalized. **Your action:** Review the OIDC (workload identity federation) federated credentials configuration that will be implemented. Ensure no secrets are stored in the workflow.

**PR #36 (Gunther):** Terraform stack with remote state backend and resource group module. **Your action:** Review infrastructure security posture alongside Ross (code review). Coordinate with Ross on approval.

### 2026-05-29T12:50:38Z — Phase 0 Batch 2 Security Review Complete

**Security Review Completed:**
- Reviewed all 7 Phase 0 PRs (#37–#43) for security posture
- 2 high-risk issues identified and resolved:
  1. PR #42 (Entra ID): Audience configuration corrected to `AzureADandPersonalMicrosoftAccount`
  2. PR #39 (CI/CD): Workflow secrets must use GitHub Secrets + OIDC, not hardcoded values
- PR #42 audience fix applied directly by Chandler
- PR #39 secrets fix applied by gunther-fixes-batch2

**Security Posture:**
- All 7 Phase 0 PRs now approved from security standpoint
- GitHub Actions use OIDC workload identity federation (no secrets in workflows)
- Entra External ID supports both enterprise and consumer accounts
- Local config ignore patterns established (.env.local, *.tfvars, backend.hcl files)
- Phase 0 security baseline complete
