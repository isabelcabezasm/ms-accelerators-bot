# Squad Decisions

## Active Decisions

### PRD Decomposition Strategy

**Date:** 2026-05-29  
**Author:** Monica (Lead)  
**Status:** Applied  

**Context:** The PRD at `docs/proposal.md` defines 6 delivery phases (0–5). We needed to decompose these into actionable, individually assignable GitHub issues.

**Decision:**
- 33 issues created across 6 phases, each scoped to a single deliverable.
- Issues labeled by phase (`phase:0`–`phase:5`), domain (`backend`, `frontend`, `infrastructure`, `security`, `testing`, `ingestion`, `data-model`), and squad member assignment.
- Dependencies documented in each issue body (not as GitHub issue links, since cross-references are cleaner once issue numbers are known).
- Phase 0 has the most issues (8) because infrastructure scaffolding has many independent modules that can be parallelized.
- Security concerns (Chandler) are co-labeled on issues where security is a first-class concern (JWT auth, WAF, GDPR, quotas, Entra ID), not isolated to a separate phase.

**Squad Assignments:**
| Member | Primary Issues |
|--------|---------------|
| Gunther (Infra) | #1–#7, #25, #29 |
| Joey (Backend) | #9–#19, #28, #30–#33 |
| Rachel (Frontend) | #8, #20–#24, #30, #32, #33 |
| Chandler (Security) | #5, #6, #13, #16, #17, #24 |
| Phoebe (Testing) | #26, #27, #29 |
| Monica (Lead) | #8 (scaffold oversight) |

**Open Item:** GitHub Project #5 integration blocked by missing `read:project` token scope. Isabel needs to refresh auth with `gh auth refresh -s read:project` to unblock.

### Cosmos DB, Key Vault, and Functions RBAC

**Date:** 2026-05-29  
**Author:** Gunther  
**Status:** Applied  

**Context:** Implementation of Cosmos DB, Key Vault, and managed storage for Functions in Phase 0.

**Decision:**
- Cosmos DB RBAC uses `azurerm_cosmosdb_sql_role_assignment` (not `azurerm_role_assignment`)
- Functions use managed identity for storage (no access keys)
- Key Vault has purge protection enabled with 90-day retention
- All access follows principle of least privilege through managed identities

**Impact:** Improved security posture and compliance readiness for data access patterns.

### Container Apps, Functions, and Static Web Apps Integration

**Date:** 2026-05-29  
**Author:** Gunther  
**Status:** Applied  

**Context:** Deployment and hosting for Phase 0 services.

**Decision:**
- Container Apps hosts the FastAPI application with managed identity
- Functions provide event-driven ingestion workloads
- Static Web Apps hosts React frontend with API proxy configuration

**Impact:** Complete Phase 0 deployment topology ready for CI/CD integration.

### Front Door and WAF Configuration

**Date:** 2026-05-29  
**Author:** Gunther  
**Status:** Applied  

**Context:** Edge security and rate limiting for public API.

**Decision:**
- Front Door rate limiting uses `/chat/` prefix (BeginsWith) for targeted protection
- WAF rules applied to chat endpoint specifically
- Rate limits configured to 1000 requests per minute per client

**Impact:** Protection for resource-intensive chat endpoint against abuse and DDoS.

### Entra External ID Audience Configuration

**Date:** 2026-05-29  
**Author:** Chandler  
**Status:** Applied  

**Context:** Multi-tenant identity for Azure Accelerators Finder.

**Decision:**
- Entra External ID uses `AzureADandPersonalMicrosoftAccount` audience
- Enables both enterprise and consumer Microsoft accounts

**Impact:** Broader user base access while maintaining security boundaries.

### GitHub Actions Workflow Security

**Date:** 2026-05-29  
**Author:** Gunther  
**Status:** Applied  

**Context:** CI/CD pipeline for Phase 0.

**Decision:**
- All GitHub Actions are pinned to commit SHAs (not version tags)
- No secrets stored in workflow files; all use GitHub Environment variables
- Workload identity federation with Azure using OIDC

**Impact:** Supply chain security and auditability for infrastructure deployments.

### AI Model Version Pinning

**Date:** 2026-05-29  
**Author:** Gunther  
**Status:** Applied  

**Context:** Reproducible and stable ML/AI behavior for Phase 0.

**Decision:**
- OpenAI `gpt-4o-mini` pinned to version `2024-07-18`
- Text embedding model `text-embedding-3-large` pinned to version `1`

**Impact:** Consistent inference behavior and reproducible results across deployments.

### Local Configuration File Ignore Patterns

**Date:** 2026-05-29  
**Author:** Chandler  
**Status:** Applied  

**Context:** Prevention of accidental secret commits in early project phases.

**Decision:**
- Ignore application environment variants: `.env.local`, `.env.*`
- Ignore Terraform local variable files: `*.tfvars`, `*.tfvars.json`, `backend.hcl`, `backend.*.hcl`
- Pattern established early to reduce risk of normalization in future PRs

**Impact:** Security baseline established before scaling contributor count.

### Scaffold Review Gates for Future Work

**Date:** 2026-05-29  
**Author:** Ross  
**Status:** Approved  

**Context:** Quality gates for future scaffold PRs.

**Decision:**
- Phase 0 scaffold PRs reviewed against full repo layout in `docs/proposal.md`
- `src/shared/` must include placeholders for shared clients, models, prompts, and auth surfaces
- Terraform scaffold PRs must validate reproducible `terraform init` and `terraform plan` flow or document exact bootstrap prerequisites

**Impact:** Foundation stability and contributor onboarding clarity.

## Governance

- All meaningful changes require team consensus
- Document architectural decisions here
- Keep history focused on work, decisions focused on direction
