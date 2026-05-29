# Project Context

- **Owner:** Isabel Cabezas
- **Project:** Microsoft Accelerators Finder — AI assistant for discovering Microsoft Accelerators using RAG (Azure AI Search + Azure OpenAI), FastAPI backend, React+Vite frontend, Entra External ID auth, Terraform IaC.
- **Stack:** Python 3.12, FastAPI, Azure AI Search, Azure OpenAI, React, Vite, TypeScript, Fluent UI, MSAL.js, Terraform, Azure Container Apps, Azure Functions, Cosmos DB, Azure Front Door + WAF
- **Created:** 2026-05-29

## Learnings

<!-- Append new learnings below. Each entry is something lasting about the project. -->

### 2026-05-29 — PRD Decomposition into GitHub Issues

Created 33 issues (#1–#33) in `isabelcabezasm/ms-accelerators-bot` from `docs/proposal.md`:

- **Phase 0 — Scaffolding (8 issues, #1–#8):** Terraform stack + remote state (#1), AI Search + OpenAI modules (#2), Cosmos DB + Blob + Key Vault (#3), Container Apps + Functions + SWA (#4), Front Door + WAF (#5), Entra External ID (#6), App Insights (#7), Repo layout scaffold (#8).
- **Phase 1 — Ingestion (4 issues, #9–#12):** Crawler for accelerators.ms (#9), GitHub README fetcher (#10), Normalize → chunk → embed pipeline (#11), Blob Storage snapshots (#12).
- **Phase 2 — Retrieval API (7 issues, #13–#19):** JWT validation middleware (#13), /search endpoint (#14), /chat endpoint with RAG (#15), Per-user quotas (#16), /me + GDPR endpoints (#17), App Insights tracing (#18), /accelerators/{id} endpoint (#19).
- **Phase 3 — Frontend (6 issues, #20–#25):** React + Vite + MSAL.js scaffold (#20), Landing page with demo search (#21), Chat page with accelerator cards (#22), History + profile pages (#23), Terms + privacy pages (#24), Custom domain via Front Door (#25).
- **Phase 4 — Evaluation (4 issues, #26–#29):** Eval test set curation (#26), Offline eval script (#27), Prompt + chunking iteration (#28), Load test + rate limit tuning (#29).
- **Phase 5 — Stretch (4 issues, #30–#33):** Compare-two-accelerators mode (#30), "Why not X?" follow-ups (#31), User feedback thumbs up/down (#32), Personalization filters (#33).

Labels created: `phase:0`–`phase:5`, `backend`, `frontend`, `infrastructure`, `security`, `testing`, `ingestion`, `data-model`. Squad member labels already existed.

**Blocked:** Could not add issues to GitHub Project #5 — the auth token lacks `read:project` scope. Isabel needs to run `gh auth refresh -s read:project` and then add the 33 issues to the project.
