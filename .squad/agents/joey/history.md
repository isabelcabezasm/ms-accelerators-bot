# Project Context

- **Owner:** Isabel Cabezas
- **Project:** Microsoft Accelerators Finder — AI assistant for discovering Microsoft Accelerators using RAG (Azure AI Search + Azure OpenAI), FastAPI backend, React+Vite frontend, Entra External ID auth, Terraform IaC.
- **Stack:** Python 3.12, FastAPI, Azure AI Search, Azure OpenAI, React, Vite, TypeScript, Fluent UI, MSAL.js, Terraform, Azure Container Apps, Azure Functions, Cosmos DB, Azure Front Door + WAF
- **Created:** 2026-05-29

## Learnings

<!-- Append new learnings below. Each entry is something lasting about the project. -->

### 2026-05-29 — PRD Decomposed into 33 GitHub Issues

Monica (Lead) created 33 issues (#1–#33) across 6 phases from `docs/proposal.md`. **Your assignments:** Backend lead (#9–#19, #28, #30–#33) — ingestion pipeline, retrieval API, chat endpoint, load testing, stretch features. See decisions.md for full details and squad assignments. **Blocked:** Project board linking needs Isabel to refresh token scope (`gh auth refresh -s read:project`).

### 2026-05-29T11:54:49.343+00:00 — Repo scaffold baseline

- Replaced the placeholder Python project with the Phase 0 skeleton in
  `src/api/`, `src/ingestion/`, `src/shared/`, and `tests/`.
- Set the backend baseline around FastAPI, `pydantic-settings`, Azure SDK
  dependencies, and shared health response models in `src/shared/models.py`.
- Added the React + Vite frontend skeleton in `frontend/` and a CI workflow
  in `.github/workflows/ci.yml` to validate backend checks and frontend
  builds.
