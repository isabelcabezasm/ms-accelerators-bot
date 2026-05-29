# Decisions Log

## 2026-05-29

### 2026-05-29T11:54: User directive — Phase 0 workflow
**By:** Isabel Cabezas (via Copilot)  
**What:** For each implementation task: create a dedicated branch and PR, attach to the issue. Move tasks to "in progress" when work starts and "in review" when the PR is opened. Ross (Code Reviewer) and Chandler (Security Expert) must review every PR before merge — add comments, approve if OK.  
**Why:** User request — captured for team memory

### 2026-05-29T11:54: CI/CD Pipeline Architecture Decision
**Date:** 2026-05-29  
**Author:** Monica (Lead)  
**Status:** Proposed  
**Issue:** #34

**Context:** We need a CI/CD pipeline to deploy Azure infrastructure via Terraform. The pipeline must be:
1. Triggered only when infrastructure files change (not on every commit)
2. Secure — using workload identity federation instead of stored secrets
3. Appropriate for Phase 0 (infrastructure scaffolding)
4. Coordinated with the Terraform scaffold work (#1)

**Decision:** Implement GitHub Actions workflow with the following architecture:
1. **Trigger:** Path-based (only on `infra/**` changes) to main and PR branches
2. **Jobs:**
   - **Plan job** (on PRs): Runs `terraform plan` and posts output as PR comment
   - **Apply job** (on merge to main): Runs `terraform init`, `terraform plan`, `terraform apply -auto-approve`
3. **Authentication:** Azure workload identity federation (OIDC) — no stored secrets
4. **State Management:** Azure Storage (configured via #1 Terraform stack scaffold)
5. **Concurrency:** Terraform state locking to prevent concurrent applies

**Rationale:**
- OIDC over secrets: Eliminates credential rotation burden, improves security audit trail, aligns with platform best practices
- Path-based triggers: Reduces noise — only infrastructure specialists care about infra pipeline runs
- Separate plan/apply jobs: Allows PR review of changes before they execute on main
- GitHub Actions + hashicorp/setup-terraform: Uses first-class GitHub integration for audit logging and security
- Phase 0 placement: Enables all subsequent infrastructure phases to deploy reliably

**Dependencies:**
- Blocks: All Phase 0 services (#2–#7) depend on this pipeline running successfully
- Depends on: #1 (Terraform stack scaffold — state backend setup)
- Coordinates with: Gunther (infra lead), Chandler (security review of OIDC setup)

**Next Steps:**
1. Gunther implements #34 (this pipeline)
2. Chandler reviews OIDC federated credentials configuration
3. Test with a PR to infra/ to verify plan output appears
4. Verify terraform apply runs and succeeds on merge to main
