# Microsoft Accelerators Finder

This repository contains the initial scaffold for the Microsoft
Accelerators Finder project described in `docs/proposal.md`.

## Repository layout

```text
src/api/        FastAPI application skeleton
src/ingestion/  Azure Functions ingestion skeleton
src/shared/     Shared models, clients, and prompts
frontend/       React + Vite + TypeScript frontend skeleton
tests/          Pytest test suite
```

## Getting started

### Backend

```bash
uv sync --dev
uv run uvicorn src.api.main:app --reload
bin/test
bin/lint/py
```

### Frontend

```bash
cd frontend
npm install
npm run build
```

## Current scaffold

- `src/api/main.py` exposes a basic `/healthz` endpoint.
- `src/api/config.py` loads settings with `pydantic-settings`.
- `src/ingestion/function_app.py` provides an Azure Functions timer stub.
- `src/shared/` holds shared Pydantic models and Azure client stubs.
- `.github/workflows/ci.yml` runs backend checks and a frontend build.
