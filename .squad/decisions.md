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

## Governance

- All meaningful changes require team consensus
- Document architectural decisions here
- Keep history focused on work, decisions focused on direction
