# Joey repo scaffold decision

- Timestamp: 2026-05-29T11:54:49.343+00:00
- Context: Issue #8 required the initial repository scaffold for the backend
  and frontend without touching `infra/`.
- Decision: Standardize the repo on a uv-managed Python 3.12 scaffold with
  FastAPI, Azure SDK placeholders, mypy + ruff + pytest checks, and a React
  + Vite + Fluent UI frontend skeleton built in CI.
- Impact: Future backend, ingestion, and frontend issues can add features on
  top of stable package, test, and workflow foundations.
