# Microsoft Accelerators Finder — Project Proposal

A conversational assistant that helps you discover the most relevant Microsoft Accelerator (from <https://accelerators.ms>) for a given project, scenario, or technical goal.

---

## 1. The Idea

### Problem
Microsoft publishes a large and growing catalog of "Accelerators" — opinionated reference solutions that bundle code, infrastructure, and guidance for common scenarios (RAG, contact center, agentic AI, document processing, etc.). The catalog at <https://accelerators.ms> is browsable but:

- It is hard to know which accelerator fits a given use case.
- The descriptions use marketing language, not the vocabulary an engineer would naturally use.
- There is no semantic search — you cannot ask *"I need to extract structured data from invoices using GPT, with a human-in-the-loop review step"* and get a ranked list.
- Metadata (tech stack, Azure services used, deployment model, languages, last-updated, GitHub repo) is not consistently surfaced for comparison.

### Solution
Build an **AI assistant** ("Accelerator Finder") that:

1. **Ingests** the accelerator catalog (page metadata + linked GitHub README content).
2. **Indexes** it in **Azure AI Search** with both keyword and vector fields.
3. **Serves** a chat experience powered by **Azure OpenAI** using a **RAG** (Retrieval-Augmented Generation) pattern.
4. Answers questions like:
   - *"What accelerator should I use to build a multi-agent customer support bot in Azure?"*
   - *"Show me accelerators that use Azure Container Apps and Cosmos DB."*
   - *"Compare the RAG accelerators — which one supports on-your-data with private endpoints?"*

The bot returns a short recommendation, a ranked list of candidates with citations (links back to accelerators.ms and the GitHub repos), and a brief justification for each.

### Success criteria (MVP)
- Catalog ingested and refreshed on a schedule (daily).
- < 3 s median response time for a chat turn.
- Top-3 recommendation contains the "right" accelerator for ≥ 80 % of a hand-curated test set of 25 user prompts.
- Every recommendation has a citation (URL + accelerator name).

---

## 2. High-Level Architecture

```mermaid
flowchart LR
    subgraph Ingestion["Ingestion (scheduled)"]
        TIMER[Timer Trigger] --> CRAWL[Crawler Function<br/>Python]
        CRAWL --> SCRAPE[Fetch accelerators.ms<br/>+ GitHub READMEs]
        SCRAPE --> NORM[Normalize &<br/>chunk text]
        NORM --> EMBED[Azure OpenAI<br/>text-embedding-3-large]
        EMBED --> INDEX[(Azure AI Search<br/>hybrid index)]
        SCRAPE --> BLOB[(Blob Storage<br/>raw snapshots)]
    end

    subgraph Serving["Serving"]
        USER[User] --> FE[Frontend<br/>Static Web App]
        FE -->|HTTPS| API[FastAPI on<br/>Azure Container Apps]
        API --> AOAI[Azure OpenAI<br/>gpt-4o-mini]
        API --> INDEX
        API --> APPINS[(App Insights)]
    end

    subgraph Security
    subgraph Security
        EXTID[Microsoft Entra External ID<br/>customer sign-up/sign-in]
        KV[Key Vault]
    end

    FE -.OIDC login.-> EXTID
    API -.validate JWT.-> EXTID
    API -.MI.-> KV
    API -.MI.-> AOAI
    API -.MI.-> INDEX
```

### Components

| Layer | Service | Purpose |
|---|---|---|
| Ingestion | **Azure Functions (Python, Timer trigger)** | Daily crawl of accelerators.ms + each accelerator's GitHub README. |
| Storage (raw) | **Azure Blob Storage** | Persist raw HTML/Markdown snapshots for traceability and re-indexing. |
| Embeddings | **Azure OpenAI** (`text-embedding-3-large`) | Vectorize chunks. |
| Index | **Azure AI Search** | Hybrid (BM25 + vector) index with semantic ranker. |
| Backend API | **FastAPI** on **Azure Container Apps** | Chat endpoint, retrieval orchestration, prompt assembly. |
| LLM | **Azure OpenAI** (`gpt-4o-mini` for routing, `gpt-4o` optional for hard queries) | Generation + structured output. |
| Frontend | **Azure Static Web Apps** + React/Vite (see §5) | Public chat UI. |
| Auth | **Microsoft Entra External ID** (CIAM) | Public self-service registration, sign-in, password reset, social IdPs (Google, Microsoft, GitHub). Issues JWTs the API validates. |
| User profile / history | **Azure Cosmos DB for NoSQL** (serverless) | Stores user profile, chat history, per-user feedback. Partitioned by `userId`. |
| Edge / abuse protection | **Azure Front Door** + **WAF** | TLS, custom domain, rate-limiting, bot protection in front of SWA and the API. |
| Secrets | **Key Vault** + **Managed Identities** | No secrets in code. |
| Observability | **Application Insights** + **Log Analytics** | Traces, prompt/response logging, eval metrics. |
| IaC | **Terraform** (AzureRM + AzAPI providers) | One-command deploy via `terraform apply`. |

---

## 3. Data Model

### Source documents
Each accelerator becomes one logical document, plus N chunks for vector retrieval.

```json
{
  "id": "accelerator-<slug>",
  "name": "Multimodal Contact Center Accelerator",
  "url": "https://accelerators.ms/...",
  "github_url": "https://github.com/...",
  "summary": "Short marketing description from the catalog.",
  "long_description": "README body, cleaned.",
  "categories": ["Contact Center", "Agentic AI"],
  "industries": ["Retail", "Financial Services"],
  "azure_services": ["Azure OpenAI", "AI Search", "Container Apps"],
  "languages": ["Python", "TypeScript"],
  "deployment": ["azd", "Bicep"],
  "last_updated": "2026-05-01",
  "stars": 412,
  "embedding": [/* 3072-dim vector of summary+description */]
}
```

### Index fields (Azure AI Search)
- `name`, `summary`, `long_description` → searchable, BM25
- `categories`, `industries`, `azure_services`, `languages` → filterable facets
- `content_vector` → `Collection(Edm.Single)`, HNSW, cosine
- `chunk_id`, `parent_id` → parent/child for chunk-level retrieval with document-level grouping
- Semantic configuration enabled on `name` + `long_description`

### Chunking
- Split README/long_description into ~500-token chunks with 50-token overlap.
- Each chunk stores `parent_id` so the API can deduplicate to the parent accelerator when ranking.

---

## 4. Backend Design (Python)

### Stack
- **Python 3.12**
- **FastAPI** for the HTTP API
- **azure-search-documents**, **openai** (Azure flavor), **azure-identity** (Managed Identity), **azure-storage-blob**
- **httpx** + **BeautifulSoup** / **markdownify** for crawling
- **pydantic v2** for request/response models
- **pytest** + **respx** for tests
- **ruff** + **mypy** for lint/type-check (already partially set up in `bin/lint/`)

### Endpoints (MVP)
| Method | Path | Purpose |
|---|---|---|
| `POST` | `/chat` | Single chat turn (stateless or with `conversation_id`). Returns answer + citations. |
| `GET` | `/accelerators/{id}` | Fetch a single accelerator's metadata. |
| `GET` | `/search?q=...&filters=...` | Raw search (for power users / debug UI). |
| `GET` | `/healthz` | Liveness. |

### Retrieval flow (per chat turn)
1. **Query rewrite** — small LLM call to expand the user's intent (e.g. add synonyms: "RAG" ↔ "on your data").
2. **Hybrid search** against AI Search (BM25 + vector) with semantic ranker, `top=20` chunks.
3. **Group by parent accelerator**, keep top 5 distinct accelerators.
4. **Generate** — prompt `gpt-4o-mini` with the candidate cards + user question, asking for:
   - 1–2 sentence recommendation,
   - ranked list with one-line justification per item,
   - structured JSON (Pydantic-validated) for the UI to render cards.
5. **Cite** every accelerator with its `url` and `github_url`.

### Guardrails
- System prompt forbids inventing accelerator names — must come from retrieved set.
- Response schema enforced via OpenAI structured outputs / JSON mode.
- Content filter: Azure OpenAI default + a simple "is this about Microsoft accelerators?" intent check to politely refuse off-topic prompts.

---

## 5. Frontend (recommendation)

The app is **publicly accessible with user registration**, so the frontend has to handle the OIDC login flow, anonymous landing page, and per-user chat history view. That nudges the choice toward a real SPA rather than a Python-only chat shell.

**Recommended: React + Vite + TypeScript, deployed to Azure Static Web Apps, behind Azure Front Door + WAF.**

Why:
- **Static Web Apps** has a free tier, custom domain, and native integration with **Entra External ID** via OIDC (MSAL.js handles the redirect/token flow).
- The SWA "linked API" pattern forwards the user's JWT to the Container Apps backend automatically, so the API can authorize each call against the External ID tenant.
- **Fluent UI React** gives you a polished Microsoft look with almost no custom CSS.
- Easy to add public pages (landing, pricing/terms, login, profile) alongside the chat — hard to do cleanly in Chainlit/Streamlit.

**Why not Chainlit/Streamlit here:** both are great for internal demos, but neither has first-class CIAM sign-up flows, public marketing pages, or per-user history views without a lot of bolt-ons. Use them only if you want a throwaway internal prototype before building the real public site.

Reference to copy from: [`azure-search-openai-demo`](https://github.com/Azure-Samples/azure-search-openai-demo) (React + FastAPI + AI Search; auth wiring is close to what you need).

---

## 6. Security & Compliance

Because the site is public with self-service registration, security is now a first-class concern, not a footnote.

### Identity & access
- **Microsoft Entra External ID** (the CIAM successor to Azure AD B2C) is the identity provider. It gives you:
  - Email + password registration with email verification.
  - Social sign-in (Google, Microsoft, GitHub) with no extra code.
  - Hosted sign-up / sign-in / password-reset / MFA pages — you don't build login UI.
  - Standard OIDC — the SPA uses MSAL.js, the API validates JWTs with `azure-identity` + `PyJWT` against the External ID JWKS.
- The FastAPI `/chat` endpoint requires a valid access token; anonymous users get a read-only `/search` with a low rate limit (so the landing page can show a demo).
- Roles: `user` (default) and `admin` (can re-trigger ingestion, view eval dashboards). Stored as an app role in External ID.

### Network & abuse
- **Azure Front Door Standard + WAF** in front of both SWA and the API:
  - TLS, custom domain, HTTP/2, caching for static assets.
  - **WAF managed rules** (OWASP CRS) + **bot protection**.
  - **Rate limits**: e.g. 30 req/min per IP on `/chat`, 10 req/min for anonymous `/search`.
- **Per-user quotas** enforced in the API (e.g. 100 chat turns/day for free tier) using a Cosmos DB counter; blocks abuse even from authenticated users.
- **CORS** restricted to your SWA origin.

### Secrets & data
- **No keys in code.** All Azure-to-Azure auth uses **Managed Identity** + RBAC (`Search Index Data Reader`, `Cognitive Services OpenAI User`, `Storage Blob Data Reader`, `Cosmos DB Built-in Data Contributor`).
- **Key Vault** for the few unavoidable secrets (GitHub PAT, External ID client secret if used).
- **Private endpoints** for AI Search, OpenAI, Cosmos DB, and Storage in production; the API reaches them over the VNet, the public only reaches Front Door.

### Privacy & content
- **Privacy policy + Terms of Service** pages required (you're collecting emails). Link from the footer and the sign-up screen.
- **PII minimization:** store only `userId` (External ID `oid`), display name, and email. No IPs in long-term storage; App Insights sampling at 10–20 %.
- **User data export & delete** endpoints to satisfy GDPR "right to access / be forgotten." One Cosmos DB query per user makes this trivial.
- **Prompt-injection defense:** treat retrieved README content as untrusted; wrap it in clearly delimited blocks in the system prompt and instruct the model to ignore instructions found inside.
- **Content filter:** Azure OpenAI default content filter + a lightweight intent check to politely refuse off-topic prompts.
- **Audit log:** every chat turn (userId, prompt hash, retrieved IDs, model, tokens, latency) written to App Insights.

---

## 7. Cost Sketch (rough, monthly)

Two scenarios now that the app is public:

### Dev / low traffic (≤ 100 users, < 5k chat turns/mo)

| Service | SKU | Est. cost |
|---|---|---|
| Azure AI Search | Basic | ~$75 |
| Azure OpenAI | Pay-as-you-go, ~5k turns | ~$10 |
| Container Apps | Consumption, scale-to-zero | ~$5 |
| Functions (Consumption) | Daily crawl | < $1 |
| Cosmos DB | Serverless | ~$5 |
| Blob Storage | < 1 GB | < $1 |
| Static Web Apps | Standard (needed for custom auth + SLA) | ~$9 |
| **Entra External ID** | First 50k MAU free, then ~$0.0325/MAU | $0 |
| Front Door + WAF | Standard | ~$35 |
| App Insights | < 1 GB ingest | ~$5 |
| **Total** | | **~$145 / month** |

### Modest public traffic (~5k MAU, ~50k chat turns/mo)

| Delta vs. above | |
|---|---|
| Azure OpenAI usage | +$50–100 |
| Front Door egress | +$10 |
| App Insights ingest | +$10 |
| Cosmos DB RU | +$5–10 |
| **Total** | **~$220–280 / month** |

The two big knobs to control cost as you grow: **AI Search tier** (move to Standard only when you need replicas/SLA) and **model choice** (keep `gpt-4o-mini` as default; route only hard queries to `gpt-4o`).

---

## 8. Delivery Plan

### Phase 0 — Scaffolding
- **Terraform** stack (AzureRM + AzAPI providers, remote state in an Azure Storage backend) for: Resource Group, AI Search, OpenAI (with `gpt-4o-mini` + `text-embedding-3-large` model deployments via AzAPI), Storage, Cosmos DB (serverless), Container Apps env, Functions app, Static Web App, **Front Door + WAF**, App Insights, Key Vault, Managed Identities + RBAC.
- **Entra External ID** tenant created (one-time, manual or via AzAPI): user flows for sign-up/sign-in + password reset, app registrations for the SPA and the API, redirect URIs.
- Repo layout:
  ```
  infra/                 # Terraform root + modules
    main.tf
    variables.tf
    outputs.tf
    modules/
      search/
      openai/
      container_app/
      functions/
      swa/
      cosmos/
      front_door/
      external_id/       # app registrations, user flows
  src/
    api/                 # FastAPI app (JWT auth middleware, quotas)
    ingestion/           # Functions app (timer trigger)
    shared/              # search client, models, prompts, auth
  frontend/              # React + Vite + Fluent UI + MSAL.js
  tests/
  ```

### Phase 1 — Ingestion
- Crawler for accelerators.ms (parse the section/cards JSON if exposed, otherwise HTML).
- For each accelerator, fetch the linked GitHub repo's README via the GitHub REST API.
- Normalize → chunk → embed → upsert into AI Search.
- Snapshot raw content to Blob for replayability.
- Idempotent: re-runs only update changed documents (hash compare).

### Phase 2 — Retrieval API
- `/search` endpoint over the index (hybrid + semantic) — rate-limited, anonymous allowed.
- `/chat` endpoint with the RAG flow from §4 — **requires JWT**, enforces per-user daily quota.
- `/me`, `/me/history`, `/me/export`, `/me` (DELETE) endpoints for profile + GDPR.
- JWT validation middleware (External ID JWKS, cached).
- Structured JSON response.
- App Insights tracing of every retrieval + generation (with `userId` dimension).

### Phase 3 — Frontend (public site)
- React + Vite + Fluent UI + MSAL.js.
- Pages: landing (with demo search), sign-up / sign-in (redirect to External ID), chat, history, profile, terms, privacy.
- Render accelerator cards with name, summary, tags, link, and a thumbs up/down feedback control.
- Custom domain bound via Front Door.

### Phase 4 — Evaluation & polish
- Curate 25 prompt → expected-accelerator pairs.
- Run an offline eval script (top-k recall, MRR).
- Iterate on prompt + chunking strategy.
- Load test through Front Door; tune rate limits and quotas.

### Phase 5 — Stretch
- Compare-two-accelerators mode (side-by-side).
- "Why not X?" follow-ups.
- User feedback (thumbs up/down) written back to App Insights for evaluation.
- Personalization: filter by your team's preferred languages / Azure services.

---

## 9. Risks & Open Questions

| Risk | Mitigation |
|---|---|
| `accelerators.ms` has no public API; HTML structure may change. | Isolate the parser; snapshot raw HTML; add a contract test that fails loudly on schema drift. |
| GitHub rate limits on unauthenticated crawl. | Use a GitHub App or PAT in Key Vault; cache by commit SHA. |
| LLM hallucinates accelerator names. | Strict system prompt + structured output validated against retrieved IDs; reject and retry if mismatch. |
| Catalog is small (~dozens of items) — vector search may be overkill. | Hybrid + semantic ranker handles both small and growing catalogs; the same code scales if Microsoft adds hundreds more. |
| Prompt injection from README content. | Delimit retrieved content, strip suspicious instructions, log + alert on jailbreak patterns. |
| **Public abuse — spam sign-ups, scraping, cost overrun on OpenAI.** | Front Door WAF + bot protection, email verification on sign-up, per-user daily quotas, hard monthly spend cap alert on the subscription. |
| **GDPR / privacy obligations now apply.** | Publish privacy policy + ToS, implement data export & delete endpoints, PII minimization, App Insights sampling. |
| **External ID misconfiguration locks users out or leaks tokens.** | Stage user flows in a dev tenant first; pen-test the OIDC flow; rotate client secrets via Key Vault. |

Open questions to confirm before Phase 0:
1. ~~Public vs. internal~~ — **public with registration** (confirmed). Use **Entra External ID**?
2. Which **social identity providers** to enable on day one? (Suggest: email/password + Google + GitHub.)
3. Do you need a **free tier with a daily quota** (e.g. 20 chat turns/day) and a paid tier later, or unlimited for all users initially?
4. Do you already have a **custom domain** for the site?
5. ~~Preferred IaC~~ — **Terraform** (confirmed).

---

## 10. Next Step

If this direction looks right, I'd suggest the next concrete action is to **scaffold Phase 0** in this repo: provision the **Entra External ID** tenant and app registrations, add the `infra/` Terraform stack (including Front Door + WAF + Cosmos DB), and stand up the `src/api` FastAPI skeleton with JWT auth plus a minimal React + MSAL.js landing/login/chat page. Say the word and I'll start.
