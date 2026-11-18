# RepoMind — Phase 12.1: Production Readiness Audit Report

**Date:** November 18, 2026  
**Auditor:** Antigravity Autonomous Agent  
**Audit Scope:** Full Application Codebase (Frontend, Backend, Database, AI Providers, Security, Deployment, Performance)  
**Status:** COMPLETE (AUDIT ONLY — No application files modified)  
**Output Document:** `docs/phase-12/repomind_phase12_1_production_readiness_audit.md`

---

## 1. Executive Summary

RepoMind underwent a comprehensive pre-deployment production readiness audit to evaluate its architectural integrity, security posture, configuration consistency, reliability, and deployment topology across Vercel (Frontend), Render (FastAPI Backend), Supabase (Managed PostgreSQL), and InstaBox (Ollama AI Inference) with Gemini API fallback.

### Key Audit Findings Overview
- **Total Findings:** 26 findings cataloged
- **Critical Blockers:** 3
- **High-Priority Issues:** 7
- **Medium-Priority Issues:** 9
- **Low-Priority Recommendations:** 7
- **Backend Test Suite:** 153/153 tests passing (100% pass rate in isolated sandbox)
- **Frontend Build:** Succeeded (`vite build` in 52.18s), but with oversized bundles and strict architectural decoupling issues

### Top Production Blockers Summary
1. **Frontend Authentication Demo Bypass (`SEC-01` / `FE-02`):** Unauthenticated visitors automatically default to `DEFAULT_DEMO_USER` (`Alex Rivera`) in `src/stores/auth.store.ts` without obtaining a JWT token. Because requests lack a valid `Bearer` token, the backend returns 401 Unauthorized, which frontend clients catch and silently replace with mock data. Real users cannot use the authenticated application cleanly.
2. **Hardcoded API Base & Proxy Dependency (`FE-01` / `DEP-02`):** Every API service in `src/services/api/` hardcodes `const API_BASE = '/api/v1'` without reading `import.meta.env.VITE_API_BASE_URL`. Production operation is 100% reliant on Vercel's rewrite rule pointing to a hardcoded Render domain (`https://repomind-backend.onrender.com`), preventing custom domains or direct cross-origin API communication.
3. **In-Memory Python-Side Vector Search (`DB-01` / `PERF-01`):** Vector embeddings are stored as raw JSON strings in a `Text` database column rather than utilizing Supabase `pgvector` indexing. On every RAG retrieval, `ChunkRepository.search_similar_chunks` loads all repository chunks into Python memory and computes cosine similarities sequentially in a Python `for` loop, presenting extreme memory and CPU exhaustion risks on Render.

---

## 2. Verified Authoritative Architecture

The code was inspected against the authoritative architecture specification:

| Component | Target Architecture | Implemented Architecture | Status / Discrepancies |
|---|---|---|---|
| **Frontend Platform** | React + Vite, deployed on Vercel | React 19 + Vite 8.3 + TailwindCSS v4 | **Verified Match** (Deployment configured via `vercel.json`) |
| **Backend Framework** | FastAPI, deployed on Render | FastAPI 0.115 + Uvicorn + Pydantic v2 | **Verified Match** (Configured via `render.yaml`) |
| **Authoritative Database** | Supabase Managed PostgreSQL | Supabase PostgreSQL via SQLAlchemy 2.0 Async + asyncpg | **Verified Match** (PostgreSQL-first with session & transaction pooling support) |
| **Primary AI Inference** | Ollama on InstaBox | Remote Ollama over HTTPS (`instabox.tech`) | **Verified Match** (`OllamaProvider` configured for InstaBox endpoint) |
| **Primary Generation Model** | `qwen3.5:4b` | `qwen3.5:4b` | **Verified Match** (Configured in `config.py` and `render.yaml`) |
| **Primary Embedding Model** | `nomic-embed-text` | `nomic-embed-text` (768-dim) | **Verified Match** (Configured in `config.py` and `code_chunk.py`) |
| **AI Fallback** | Gemini API Free Tier | `GeminiProvider` (`generativelanguage.googleapis.com`) | **Verified Match** (Only triggered on recoverable primary failures) |
| **Frontend -> Backend Comms** | Direct / Rewritten to FastAPI | Hardcoded `/api/v1` via Vite Proxy / Vercel Rewrites | **Partial Deviation** (Lacks dynamic `VITE_API_BASE_URL`) |
| **FastAPI -> Supabase & AI** | Backend calls DB and AI providers | Asyncpg connection pool + Httpx clients | **Verified Match** |

### Obsolete and Conflicting Infrastructure
- **Root `.env.example`:** Retains obsolete Google Cloud Run / AI Studio boilerplate (`APP_URL="MY_APP_URL"`, `GEMINI_API_KEY`) without declaring frontend environment variables (`VITE_API_BASE_URL`).
- **`package.json` Vestigial Packages:** Contains unused packages: `express`, `@types/express`, `dotenv`, and `@google/genai` (direct frontend SDK not utilized, as all AI inference is proxied through FastAPI).
- **Duplicate Render Blueprint:** Both `./render.yaml` and `./backend/render.yaml` exist, with differing `rootDir` directives.

---

## 3. Frontend Production Audit

### Detailed Analysis
The frontend is a single-page application built with React 19, TypeScript, Vite, Tailwind CSS, TanStack Query, and Zustand. 

#### Findings:

##### `FE-01` — Hardcoded Relative API Base URL in Frontend Service Modules
- **Severity:** Critical
- **Classification:** Verified issue
- **File & Code Location:** `src/services/api/*.ts` (11 files including `auth.api.ts:5`, `repository.api.ts:10`, `assistant.api.ts:5`, `architecture.api.ts:5`, `dependency.api.ts:5`, `documentation.api.ts:5`, `execution.api.ts:9`, `explorer.api.ts:5`, `updates.api.ts:10`)
- **Observed Behavior:** Each API client hardcodes `const API_BASE = '/api/v1';`. None of the modules inspect `import.meta.env.VITE_API_BASE_URL` or `import.meta.env.VITE_API_URL`.
- **Why it matters in production:** If the Vercel rewrite fails, if Vercel preview URLs are used, or if the user deploys the frontend to Cloudflare Pages, S3, or GitHub Pages, all API requests fail. The frontend cannot be configured to point directly to Render's backend domain.
- **Recommended Correction:** Create a centralized API configuration utility `src/services/api/config.ts` defining `export const API_BASE = (import.meta.env.VITE_API_BASE_URL || '/api/v1').replace(/\/+$/, '');` and refactor all API services to import it.
- **Verification Method:** Inspect network tab in production build; confirm that custom `VITE_API_BASE_URL` prefixes all outbound HTTP requests.

##### `FE-02` — Default Demo Session Bypasses Authentication Gate
- **Severity:** Critical
- **Classification:** Verified issue
- **File & Code Location:** `src/stores/auth.store.ts:26-44`
- **Observed Behavior:** `getInitialUser()` returns `DEFAULT_DEMO_USER` (`Alex Rivera`) whenever `localStorage.getItem('repomind-auth-session')` is missing. As a result, `isAuthenticated` defaults to `true` on first visit.
- **Why it matters in production:** Real unauthenticated visitors never see the Login or Landing pages as intended. Instead, they land directly in `/dashboard` as "Alex Rivera". Because no actual JWT access token exists in `localStorage`, backend API calls fail with 401 Unauthorized, triggering silent fallbacks to fake mock datasets.
- **Recommended Correction:** Modify `getInitialUser()` to return `null` unless a valid stored session and token exist. Unauthenticated users must land on the Landing or Login page.
- **Verification Method:** Clear browser local storage in an incognito window, open `/dashboard`, and verify redirection to `/login`.

##### `FE-03` — Silent Mock Data Fallback Masks Backend Outages
- **Severity:** High
- **Classification:** Verified issue
- **File & Code Location:** `src/services/api/repository.api.ts:74, 90, 104, 135, 203`, `src/services/api/assistant.api.ts:24, 50, 90`, `src/services/api/architecture.api.ts:24, 30`
- **Observed Behavior:** In catch blocks and `!res.ok` branches, API methods catch errors and silently return `mockRepositoryService.getRepositories()`, `mockAssistantService.getConversations()`, etc.
- **Why it matters in production:** If the Render backend spins down, fails a health check, encounters a 500 error, or rejects a token with 401, the user is never notified of the error. Instead, mock repositories and responses are rendered, creating a false impression of system health and masking critical backend faults.
- **Recommended Correction:** Remove silent mock service fallbacks from `src/services/api/`. Throw descriptive errors that TanStack Query and UI `ErrorState` components can display to the user with retry buttons.
- **Verification Method:** Terminate the backend server, navigate to `/repositories`, and verify that an error banner/toast is shown rather than mock data.

##### `FE-04` — Complete Absence of JWT Token Refresh Logic
- **Severity:** High
- **Classification:** Verified issue
- **File & Code Location:** `src/services/api/auth.api.ts:43-45`, `src/services/api/repository.api.ts:12-16`
- **Observed Behavior:** `repomind_refresh_token` is saved to `localStorage` on login and removed on logout, but is never used anywhere else. There is no HTTP client interceptor or 401 handler that calls `POST /api/v1/auth/refresh`.
- **Why it matters in production:** The backend access token expires after 30-60 minutes (`ACCESS_TOKEN_EXPIRE_MINUTES`). Once expired, every subsequent user action fails or drops to mock data, requiring manual logout and re-login.
- **Recommended Correction:** Implement an HTTP fetch wrapper / interceptor that traps 401 responses, calls `POST /api/v1/auth/refresh` with the refresh token, updates `localStorage`, and retries the original request.
- **Verification Method:** Set `ACCESS_TOKEN_EXPIRE_MINUTES=1`, wait 65 seconds, trigger an action in the UI, and verify seamless continuation without re-login.

##### `FE-05` — Ingestion Simulation & Missing Binary ZIP Upload
- **Severity:** High
- **Classification:** Verified issue
- **File & Code Location:** `src/features/repositories/AddRepositoryPage.tsx:145-175`, `src/services/api/repository.api.ts:173-195`
- **Observed Behavior:** `AddRepositoryPage.tsx` simulates indexing with a client-side `setTimeout` loop. Submitting a ZIP file sends a dummy string `url: zip://${zipFile.name}` as JSON to `POST /api/v1/repositories`. The backend rejects this because it expects a valid GitHub URL, which triggers the frontend catch block and falls back to mock data. The real multipart upload endpoint `POST /api/v1/repositories/upload` is never invoked.
- **Why it matters in production:** Users cannot upload actual repository ZIP files to RepoMind. Ingestion in the UI remains a client-side mock simulation.
- **Recommended Correction:** Implement `uploadRepositoryZip(file: File, name?: string)` in `repository.api.ts` using `FormData` and `POST /api/v1/repositories/upload`. Update `AddRepositoryPage.tsx` to call this method and track real job progress via `GET /api/v1/repositories/{id}/overview`.
- **Verification Method:** Upload a valid test `.zip` file from the UI; verify `POST /api/v1/repositories/upload` returns 201 and ingestion commences.

##### `FE-06` — File Explorer Content Hardcoded to Mock Implementation
- **Severity:** High
- **Classification:** Verified issue
- **File & Code Location:** `src/services/api/explorer.api.ts:53-59`
- **Observed Behavior:** `getFileIntelligence` in `ApiExplorerService` queries `/symbols?search=...`, ignores the response, and unconditionally executes `return mockExplorerService.getFileIntelligence(repositoryId, filePath);`.
- **Why it matters in production:** Clicking any file in the Code Explorer view always renders hardcoded mock file contents (`// Sample file preview: ...`) regardless of what is actually in the repository.
- **Recommended Correction:** Connect `getFileIntelligence` to the backend endpoint returning file symbols, imports, and AST data.
- **Verification Method:** Select a source file in Explorer and confirm real syntax tree symbols appear in the inspector panel.

##### `FE-07` — `settingsService` Hardcoded to Mock
- **Severity:** Medium
- **Classification:** Verified issue
- **File & Code Location:** `src/services/index.ts:42`, `src/services/mock/settings.mock.ts`
- **Observed Behavior:** `export const settingsService: SettingsService = mockSettingsService;`. No real API client exists for settings.
- **Why it matters in production:** Health checks run on the `/settings` page test mock status rather than querying `GET /api/v1/health` and `GET /api/v1/health/ai-providers`.
- **Recommended Correction:** Implement `ApiSettingsService` that invokes `/api/v1/health` and `/api/v1/health/ai-providers`.
- **Verification Method:** Open `/settings` and verify latency metrics reflect live provider health.

##### `FE-08` — Phase 1 Mock Banners Present in Production UI
- **Severity:** Medium
- **Classification:** Verified issue
- **File & Code Location:** `src/features/repositories/AddRepositoryPage.tsx:189`, `src/features/assistant/AssistantPage.tsx:159`, `src/features/settings/SettingsPage.tsx:132`
- **Observed Behavior:** `SampleDataBanner` components with text like `"Phase 1 Ingestion Simulation..."`, `"Sample Phase 1 Assistant..."`, and `"Phase 1 Mock Settings..."` are rendered permanently.
- **Why it matters in production:** Misleads production users and conveys an unfinished prototype impression.
- **Recommended Correction:** Remove or conditionally disable `SampleDataBanner` components when `import.meta.env.PROD` is true.
- **Verification Method:** Verify absence of mock banners in production build.

##### `FE-09` — GitHub Sign-in Unconditionally Mocked
- **Severity:** Medium
- **Classification:** Verified issue
- **File & Code Location:** `src/services/api/auth.api.ts:126-128`, `src/features/auth/LoginPage.tsx:213`
- **Observed Behavior:** `loginWithGitHub` directly delegates to `mockAuthService.loginWithGitHub()`.
- **Why it matters in production:** "Sign in with GitHub" logs the user in as a fake user without contacting GitHub or backend OAuth endpoints.
- **Recommended Correction:** Initiate GitHub OAuth via `GET /api/v1/auth/github/connect` or hide GitHub login button until OAuth redirect handler is completed.
- **Verification Method:** Click "Sign in with GitHub" and verify redirect to `github.com/login/oauth/authorize`.

##### `FE-10` — Large Production Bundle Sizes
- **Severity:** Low
- **Classification:** Verified issue
- **File & Code Location:** `vite.config.ts`, `dist/assets/`
- **Observed Behavior:** Output chunks exceed 500kB: `elk-XV6XMXQE-D-3Tg25Q.js` (1.5MB uncompressed, 465kB gzip), `cytoscape.esm-nTrd5EVq.js` (441kB), `index--_AI4-1h.js` (659kB).
- **Why it matters in production:** Slows initial load on mobile or high-latency connections.
- **Recommended Correction:** Ensure `@xyflow/react`, `elkjs`, and `cytoscape` are lazy-loaded only when Architecture and Execution views are mounted.
- **Verification Method:** Check network bundle payload on `/` and `/dashboard`.

---

## 4. Backend Production Audit

### Detailed Analysis
The backend is a FastAPI application structured with layered modular architecture: `api/v1/endpoints/`, `services/`, `repositories/`, `models/`, and `core/`.

#### Findings:

##### `BE-01` — Lifespan Uses `Base.metadata.create_all` Instead of Alembic Migrations
- **Severity:** High
- **Classification:** Verified issue
- **File & Code Location:** `backend/app/main.py:28-38`, `render.yaml:7-8`
- **Observed Behavior:** Startup executes `await conn.run_sync(Base.metadata.create_all)`. `render.yaml` buildCommand is `pip install -r requirements.txt` without `alembic upgrade head`.
- **Why it matters in production:** `create_all` does not perform schema alterations, add new columns, modify constraints, or populate the `alembic_version` table. If tables already exist, `create_all` does nothing, leading to drift between the codebase models and production database schema.
- **Recommended Correction:** Update `render.yaml` buildCommand: `pip install -r requirements.txt && alembic upgrade head`. Replace `Base.metadata.create_all` in `main.py` with an optional migration check or remove DDL from the runtime web path.
- **Verification Method:** Inspect Supabase database; verify `alembic_version` contains `e5f6a7b8c9d0`.

##### `BE-02` — Ephemeral Filesystem Storage for Repository Workspaces
- **Severity:** High
- **Classification:** Verified issue
- **File & Code Location:** `backend/app/services/workspace_service.py:15-18`, `backend/app/core/config.py:53`
- **Observed Behavior:** Repositories are extracted to `./storage/workspaces/{user_id}/{repo_id}`. On Render web services, the local filesystem is ephemeral and reset on restarts and redeployments.
- **Why it matters in production:** When Render restarts the container (e.g., after an idle period or deploy), all on-disk repository files and baseline snapshots are wiped. Features requiring physical source files (such as incremental symbol diffs in `UpdateService` or AST re-parsing) will encounter `FileNotFoundError` unless the repository can be re-fetched from GitHub. For ZIP-uploaded repositories, the source ZIP was already deleted (`ingestion_service.py:276`), making recovery impossible.
- **Recommended Correction:** For production, configure Render Persistent Disks mounted at `/var/data/repomind/storage` via `render.yaml`, or persist compressed source archives in Supabase Storage buckets.
- **Verification Method:** Trigger ingestion, restart container, and verify workspace persistence.

##### `BE-03` — No Recovery Mechanism for Interrupted Ingestion Jobs
- **Severity:** Medium
- **Classification:** Verified issue
- **File & Code Location:** `backend/app/services/ingestion_service.py:44, 86`, `backend/app/main.py:21-44`
- **Observed Behavior:** If the server container terminates while an ingestion job is in progress, the database record remains permanently in status `"ingesting"`, `"cloning"`, or `"analyzing"`. On startup, no check exists to mark interrupted jobs as `"failed"`.
- **Why it matters in production:** The repository remains locked in an `ingesting` state forever. Subsequent ingestion attempts are blocked by `create_job` (`if latest and latest.status in (...) return latest`).
- **Recommended Correction:** In `lifespan` startup, execute a query resetting any active jobs older than 15 minutes to `"failed"` with error `"Ingestion interrupted by server restart"`.
- **Verification Method:** Start an ingestion, kill the server process, restart, and verify the job status transitions to `failed` allowing retry.

##### `BE-04` — Missing `--proxy-headers` in Uvicorn Start Command
- **Severity:** Medium
- **Classification:** Verified issue
- **File & Code Location:** `render.yaml:8`, `backend/render.yaml:7`
- **Observed Behavior:** `startCommand: uvicorn app.main:app --host 0.0.0.0 --port $PORT`.
- **Why it matters in production:** Render routes requests through an ingress reverse proxy. Without `--proxy-headers --forwarded-allow-ips='*'`, Uvicorn does not unpack `X-Forwarded-For` and `X-Forwarded-Proto`. As a result, SlowAPI rate limiting (`key_func=get_remote_address`) sees the Render proxy IP for all users, potentially applying the 200 req/min rate limit collectively across all visitors.
- **Recommended Correction:** Update startCommand: `uvicorn app.main:app --host 0.0.0.0 --port $PORT --proxy-headers --forwarded-allow-ips='*'`.
- **Verification Method:** Inspect `X-Request-ID` logs; verify `request.client.host` matches real external IP rather than 10.x.x.x.

##### `BE-05` — GitHub OAuth Callback Requires Bearer Token on Browser GET
- **Severity:** Medium
- **Classification:** Verified issue
- **File & Code Location:** `backend/app/api/v1/endpoints/github.py:38-43`
- **Observed Behavior:** `github_oauth_callback` declares `current_user: User = Depends(get_current_user)`.
- **Why it matters in production:** When GitHub redirects the user's browser back to the callback URL (`/api/v1/auth/github/callback?code=...&state=...`), the browser performs a top-level GET without an `Authorization: Bearer <token>` header, resulting in immediate 401 Unauthorized.
- **Recommended Correction:** The OAuth callback should be handled by a frontend route (e.g. `/auth/github/callback`) which extracts `code` and `state`, reads the stored user token, and posts to a backend exchange endpoint with the Bearer token; or the callback state should encode a short-lived signed session ticket.
- **Verification Method:** Trace the OAuth redirect flow and confirm token exchange succeeds without 401.

##### `BE-06` — Health Check Always Returns HTTP 200 on Database Disconnect
- **Severity:** Low
- **Classification:** Verified issue
- **File & Code Location:** `backend/app/api/v1/endpoints/health.py:42-50`
- **Observed Behavior:** `api_v1_health` returns `HealthCheckResponse(status="degraded", database="disconnected")` with HTTP status 200 OK when `check_db_health()` returns `False`.
- **Why it matters in production:** Render checks `healthCheckPath: /api/v1/health` for an HTTP 200 response to determine instance readiness. If the database is completely unreachable, Render will still consider the instance healthy and route live user traffic to it.
- **Recommended Correction:** If `not db_ok`, return HTTP 503 Service Unavailable so Render delays traffic routing until database connectivity is verified.
- **Verification Method:** Provide invalid `DATABASE_URL`; verify `/api/v1/health` returns status 503.

---

## 5. Supabase Database Audit

### Detailed Analysis
The application uses Supabase-managed PostgreSQL as its single authoritative database.

#### Findings:

##### `DB-01` — In-Memory Python-Side Cosine Similarity Calculation
- **Severity:** Critical
- **Classification:** Verified issue
- **File & Code Location:** `backend/app/models/code_chunk.py:53`, `backend/app/repositories/chunk_repository.py:81-100`
- **Observed Behavior:** Embedding vectors are stored as stringified JSON lists in a `Text` column: `embedding_json: Mapped[str] = mapped_column(Text)`. Vector search in `ChunkRepository.search_similar_chunks` executes:
  ```python
  res = await self.session.execute(select(CodeChunk).options(selectinload(CodeChunk.file)).where(CodeChunk.repository_id == repo_id))
  chunks = list(res.scalars().all())
  for chunk in chunks:
      chunk_vec = chunk.embedding_vector  # json.loads(...)
      sim = cosine_similarity(query_embedding, chunk_vec)
  ```
- **Why it matters in production:** In a medium repository with 5,000 code chunks, every user question in the Assistant loads all 5,000 chunks (several megabytes of text and JSON) from Supabase across the network into Render's memory, deserializes 5,000 JSON strings into Python lists, and calculates 5,000 dot products in a single-threaded Python loop. This leads to high memory spikes, latency exceeding 5-10 seconds per RAG query, and eventual OOM crashes on Render's 512MB free tier or starter plans.
- **Recommended Correction:** Migrate `embedding_json` to a native PostgreSQL `vector(768)` column using Supabase's enabled `pgvector` extension. Execute vector similarity queries directly in SQL (`ORDER BY embedding <=> :query_vector LIMIT :top_k`).
- **Verification Method:** Run a similarity search against 2,000 chunks; measure latency reduction from >3s in Python to <30ms in PostgreSQL.

##### `DB-02` — Supabase Connection Mode Selection for Render
- **Severity:** Medium
- **Classification:** Potential issue requiring external verification
- **File & Code Location:** `backend/.env.example:14-20`, `backend/app/db/session.py:36-47`
- **Observed Behavior:** Session.py detects `:6543` and disables prepared statements (`statement_cache_size=0`), supporting Supavisor transaction pooling. However, direct connections on port 5432 (`db.[ref].supabase.co:5432`) are presented as the primary default.
- **Why it matters in production:** Direct connections to `db.[ref].supabase.co` on port 5432 resolve to IPv6 addresses. If Render's web service instance is in an environment without outgoing IPv6 routes, connection attempts fail with timeout. Furthermore, direct connections consume PostgreSQL server process slots rapidly under concurrent traffic. Supabase transaction pooler on port 6543 is safer for connection scaling.
- **Recommended Correction:** Document that Render deployments should use the Supabase Transaction Pooler URL (`aws-0-[region].pooler.supabase.com:6543`) with `ssl=require`.
- **Verification Method:** Test connection from Render instance shell to both port 5432 and port 6543.

##### `DB-03` — Lack of Database-Level Row Level Security (RLS)
- **Severity:** Medium
- **Classification:** Verified issue
- **File & Code Location:** `backend/migrations/versions/*.py`
- **Observed Behavior:** Tables are created without `ALTER TABLE ... ENABLE ROW LEVEL SECURITY;`. All isolation is enforced at the application query level (`where(Repository.owner_id == user_id)`).
- **Why it matters in production:** While application-level checks are verified and unit tested, connecting to Supabase directly or accidentally exposing an anon key with PostgREST enabled would allow public reading of all repository data without RLS policies.
- **Recommended Correction:** Enable RLS on all tables and create policies or ensure Supabase PostgREST API access is restricted.
- **Verification Method:** Query Supabase table via Supabase client without service role; verify access is restricted.

---

## 6. AI Provider Audit

### Detailed Analysis
The application uses a primary/fallback AI architecture:
- **Primary:** Ollama on InstaBox (`https://11434-agq6j3olyzqnjz6i3vl5zgyvj4.instabox.tech`)
- **Fallback:** Google Gemini Free Tier (`gemini-1.5-flash`)

#### Findings:

##### `AI-01` — Single Point of Failure on Embedding Generation
- **Severity:** High
- **Classification:** Verified issue
- **File & Code Location:** `backend/app/ai/gemini_provider.py:187-206`, `backend/app/services/rag_service.py:105-108`
- **Observed Behavior:** `GeminiProvider.generate_embedding` explicitly raises `NotImplementedError("Embeddings must be generated using Ollama nomic-embed-text for consistent dimensions.")`.
- **Why it matters in production:** While this design correctly prevents mixing 768-dim `nomic-embed-text` with incompatible embedding models, it means that if the InstaBox Ollama instance is asleep, paused, or down, RAG retrieval fails completely: queries cannot be embedded, and repositories cannot be ingested. Gemini fallback is available for text generation, but NOT for embeddings.
- **Recommended Correction:** Implement an alert mechanism when Ollama is unreachable. If Ollama sleep/hibernation is common on InstaBox, consider keeping the instance warm or providing a standby embedding service.
- **Verification Method:** Simulate Ollama down during chat query; observe that generation fallback cannot proceed if vector retrieval fails.

##### `AI-02` — InstaBox CPU Latency & Timeout Boundaries
- **Severity:** Medium
- **Classification:** Potential issue requiring external verification
- **File & Code Location:** `backend/app/core/config.py:95-96`, `backend/app/ai/ollama_provider.py:66-70`
- **Observed Behavior:** Default generation timeout is 60.0s (`OLLAMA_TIMEOUT_SECONDS = 60.0`), with connect timeout 10.0s.
- **Why it matters in production:** InstaBox instances typically run on shared vCPU. Generating large documentation chapters or processing long RAG prompts with `qwen3.5:4b` at 4096 context tokens on CPU can take 45-80 seconds. Ingestion of 1,000 chunks in batches of 16 takes 60+ sequential HTTP requests.
- **Recommended Correction:** Increase `OLLAMA_TIMEOUT_SECONDS` to 120.0s for documentation generation and batch embedding, and tune `EMBEDDING_BATCH_SIZE` dynamically based on latency.
- **Verification Method:** Run a benchmark generation with 3,500 input tokens on InstaBox and record response duration.

##### `AI-03` — Gemini Model Name Formatting Discrepancy
- **Severity:** Medium
- **Classification:** Verified issue
- **File & Code Location:** `backend/.env.example:60`, `backend/app/core/config.py:101`, `render.yaml:50`
- **Observed Behavior:** `backend/.env.example:60` specifies `GEMINI_MODEL=gemini 3.8 Flash` (containing spaces and a non-standard name), whereas `config.py` and `render.yaml` specify `gemini-1.5-flash`.
- **Why it matters in production:** Copying `.env.example` into a production environment variable will cause Gemini API calls to fail with 404 Model Not Found.
- **Recommended Correction:** Standardize `.env.example` to `GEMINI_MODEL=gemini-1.5-flash`.
- **Verification Method:** Verify Gemini health check endpoint `/api/v1/health/ai-providers` passes with configured model.

##### `AI-04` — Secret Sanitization and Prompt Injection Defenses
- **Severity:** Low
- **Classification:** No issue found / Verified working
- **File & Code Location:** `backend/app/ai/provider_manager.py:23-32, 70-76`, `backend/app/services/rag_service.py:68-76`
- **Observed Behavior:** `ProviderManager.sanitize_text_for_cloud` redacts API keys, passwords in DB URLs, GitHub PATs (`ghp_`), and JWT tokens before sending any prompt to Gemini cloud fallback. `RAGService` isolates code evidence inside XML delimiters and neutralizes closing tags.
- **Verification Method:** Tested in `test_phase11_security_hardening.py` (passes).

---

## 7. Security Audit

### Detailed Analysis
The application was audited against OWASP Top 10 API Security Risks:

#### Findings:

##### `SEC-01` — Frontend `localStorage` Token Storage Security Risks
- **Severity:** High
- **Classification:** Verified issue
- **File & Code Location:** `src/services/api/auth.api.ts:42-45, 133, 151`
- **Observed Behavior:** Both `repomind_access_token` and `repomind_refresh_token` are written directly to `window.localStorage`.
- **Security Implications in Production:**
  1. **XSS Exposure:** Any Cross-Site Scripting vulnerability in frontend dependencies or inline scripts grants immediate access to the 7-day refresh token, allowing total account takeover.
  2. **Persistence across Sessions:** Unlike `sessionStorage`, `localStorage` persists indefinitely on shared machines unless explicitly cleared by logout.
- **Recommended Correction:** Store `access_token` in memory (Zustand store or React ref). Store `refresh_token` in an `HttpOnly`, `Secure`, `SameSite=Strict` cookie managed by the backend during `/auth/login` and `/auth/refresh`.
- **Verification Method:** Inspect browser cookies vs local storage; confirm refresh tokens are inaccessible via `document.cookie` or `window.localStorage`.

##### `SEC-02` — CORS Allowed Origins Configuration for Production
- **Severity:** Medium
- **Classification:** Verified issue
- **File & Code Location:** `render.yaml:31-32`, `backend/app/core/config.py:23-27`
- **Observed Behavior:** `ALLOWED_ORIGINS` in `render.yaml` is set to `'["https://repomind.vercel.app","http://localhost:5173","http://localhost:3000"]'`.
- **Why it matters in production:** If Vercel assigns a preview URL (e.g. `https://repomind-git-main-user.vercel.app`) or a different production domain (e.g. `https://repomind-ai.vercel.app`), browser CORS preflight requests will be rejected by FastAPI with 403 Forbidden.
- **Recommended Correction:** Support wildcard regex or comma-separated origins including `*.vercel.app` in `ALLOWED_ORIGINS` or ensure the exact production Vercel domain matches the environment variable.
- **Verification Method:** Send an `OPTIONS` request with `Origin: https://repomind-preview.vercel.app` and verify whether `Access-Control-Allow-Origin` is returned.

##### `SEC-03` — ZIP Slip and Path Traversal Defenses
- **Severity:** Low
- **Classification:** No issue found / Verified working
- **File & Code Location:** `backend/app/services/zip_service.py:12-145`
- **Observed Behavior:** Thorough defense implementation:
  - Magic bytes header validation (`PK\x03\x04`).
  - CRC32 integrity test via `archive.testzip()`.
  - Max file count limit (10,000 files).
  - Max uncompressed size limit (250MB).
  - Zip bomb ratio detection (`ratio > 100`).
  - Symlink detection and rejection (`0o120000`).
  - Double path containment check via `target_path.relative_to(destination_dir)`.
- **Verification Method:** Verified by 4 unit tests in `test_phase3_zip_security.py` (all pass).

##### `SEC-04` — Password Hashing and Token Signing
- **Severity:** Low
- **Classification:** No issue found / Verified working
- **File & Code Location:** `backend/app/core/security.py:12-32`, `backend/app/core/crypto.py:8-44`
- **Observed Behavior:** Argon2id is used with standard cryptographic parameters (`time_cost=3, memory_cost=65536, parallelism=4`). JWT uses HS256 with distinct `jti` and type claims (`access` vs `refresh`). GitHub OAuth tokens are encrypted at rest with Fernet symmetric encryption.
- **Verification Method:** Verified in `test_auth.py` (all 11 tests pass).

---

## 8. Deployment Configuration Audit

### Detailed Analysis
Inspection of `vercel.json`, `render.yaml`, and `backend/render.yaml`:

#### Findings:

##### `DEP-01` — Duplicate and Inconsistent `render.yaml` Specifications
- **Severity:** High
- **Classification:** Verified issue
- **File & Code Location:** `./render.yaml` vs `./backend/render.yaml`
- **Observed Behavior:** Root `render.yaml` includes `rootDir: backend`. `backend/render.yaml` omits `rootDir: backend`.
- **Why it matters in production:** Render Blueprint sync reads the root `render.yaml`. If a developer or automated hook references `backend/render.yaml`, the build directory context will conflict, leading to failed builds.
- **Recommended Correction:** Delete `backend/render.yaml` and retain root `render.yaml` as the single authoritative blueprint.
- **Verification Method:** Run Render blueprint validation.

##### `DEP-02` — Hardcoded Render Destination in `vercel.json` Rewrite
- **Severity:** High
- **Classification:** Verified issue
- **File & Code Location:** `vercel.json:6-10`
- **Observed Behavior:**
  ```json
  "rewrites": [
    {
      "source": "/api/v1/:path*",
      "destination": "https://repomind-backend.onrender.com/api/v1/:path*"
    }
  ]
  ```
- **Why it matters in production:** If the Render service is created under any other name (e.g. `repomind-api`, `repomind-backend-app`, or on a custom domain), Vercel routes all API traffic to a dead URL. Because `destination` cannot reference Vercel environment variables directly in `vercel.json`, this hardcoded string is fragile.
- **Recommended Correction:** Ensure the frontend API client connects directly to `VITE_API_BASE_URL` with proper CORS headers rather than relying exclusively on Vercel rewrites.
- **Verification Method:** Check API network requests from deployed Vercel domain.

##### `DEP-03` — Vercel Rewrite Body Limit vs ZIP Upload Limits
- **Severity:** Medium
- **Classification:** Potential issue requiring external verification
- **File & Code Location:** `vercel.json:8-10`, `backend/app/core/config.py:54`
- **Observed Behavior:** Backend allows 50MB ZIP uploads (`MAX_UPLOAD_SIZE_BYTES = 52428800`). However, Vercel serverless / edge rewrites enforce payload limits (often 4.5MB for serverless functions).
- **Why it matters in production:** Uploading a 15MB repository ZIP through the Vercel rewrite proxy `/api/v1/...` will be aborted by Vercel with HTTP 413 Payload Too Large before reaching Render.
- **Recommended Correction:** For repository uploads and large payloads, configure the frontend to submit directly to Render's backend domain (`https://repomind-backend.onrender.com/api/v1/repositories/upload`) with CORS credentials, bypassing Vercel's rewrite proxy.
- **Verification Method:** Upload a 10MB test ZIP through the rewrite and verify whether Vercel passes or rejects it.

##### `DEP-04` — Missing `.python-version` Specification
- **Severity:** Low
- **Classification:** Verified issue
- **File & Code Location:** Root and `backend/` directories
- **Observed Behavior:** No `.python-version` or `runtime.txt` exists in `backend/`.
- **Why it matters in production:** Render will default to whatever Python version is active on its build image (which may be 3.12 or 3.10), whereas local development and testing was performed on Python 3.11.9. Package compatibility (e.g. with `tree-sitter-languages` and `asyncpg`) can vary across minor Python versions.
- **Recommended Correction:** Add `.python-version` with content `3.11.9` in `backend/`.
- **Verification Method:** Verify Render build log displays `Using Python version 3.11.9`.

---

## 9. Performance and Reliability Audit

### Detailed Analysis
Inspection of system bottlenecks during large repository ingestion and querying:

#### Findings:

##### `PERF-01` — RAG Retrieval Complexity is $O(N)$ Over Total Repository Chunks
- **Severity:** High
- **Classification:** Verified issue
- **File & Code Location:** `backend/app/repositories/chunk_repository.py:81-100`
- **Observed Behavior:** `search_similar_chunks` loads all rows from `code_chunks` for `repository_id` into Python memory and iterates through each row.
- **Why it matters in production:** Linear memory and CPU consumption on Render. If a repository has 4,000 chunks, a single chat query loads ~20MB of text and executes 4,000 vector similarity checks in Python. Under concurrent requests, Render container memory will spike and trigger restarts.
- **Recommended Correction:** Move vector similarity search to PostgreSQL via `pgvector` (`<=>` cosine distance operator).
- **Verification Method:** Benchmark RAG retrieval with 5,000 chunks in database.

##### `PERF-02` — Sequential Batch Embedding Dispatch
- **Severity:** Medium
- **Classification:** Verified issue
- **File & Code Location:** `backend/app/services/embedding_service.py:77-82`
- **Observed Behavior:** Chunks are grouped into batches of 16 (`EMBEDDING_BATCH_SIZE = 16`) and sent sequentially to Ollama via `await self.provider_manager.generate_embeddings_batch(...)`.
- **Why it matters in production:** For 1,000 chunks, 63 sequential HTTP calls are made. Over remote HTTPS to InstaBox with ~1.5s latency per batch, embedding generation alone takes over 90 seconds.
- **Recommended Correction:** Introduce bounded concurrent batching (e.g., `asyncio.gather` with a semaphore of 2-3 concurrent batches) to reduce total embedding indexing time by 50-60%.
- **Verification Method:** Measure total indexing time for a 50-file repository before and after concurrency.

##### `PERF-03` — Render Free/Standard Cold Start Timeout
- **Severity:** Medium
- **Classification:** Potential issue requiring external verification
- **File & Code Location:** `render.yaml:6` (`plan: standard`)
- **Observed Behavior:** `render.yaml` specifies `plan: standard`. However, if deployed on Render's free tier, instances spin down after 15 minutes of inactivity. Cold starts take 50+ seconds.
- **Why it matters in production:** Vercel rewrites time out after 15-30 seconds. A cold start on Render can cause initial visits on Vercel to fail with 504 Gateway Timeout.
- **Recommended Correction:** Maintain `plan: standard` (or starter paid plan) to prevent spin-down, or implement a frontend ping/wake-up mechanism with loading indicator.
- **Verification Method:** Test initial request after 20 minutes of instance inactivity.

---

## 10. Critical Production Blockers

These 3 issues **MUST** be resolved before any deployment:

| ID | Category | Summary | Impact |
|---|---|---|---|
| **SEC-01 / FE-02** | Security / Auth | Default Demo User session in `auth.store.ts` | All unauthenticated visitors bypass login, receive 401s, and see broken mock states. |
| **FE-01 / DEP-02** | Frontend / Deploy | Hardcoded `API_BASE = '/api/v1'` across all services | Frontend cannot connect to Render backend directly or across custom domains. |
| **DB-01 / PERF-01** | Database / Perf | In-memory Python cosine similarity instead of `pgvector` | Severe memory spikes and latency degradation on Render during RAG queries. |

---

## 11. High-Priority Issues

Must be resolved prior to public release or beta launch:

| ID | Component | Summary | Recommended Fix |
|---|---|---|---|
| **FE-03** | Frontend | Silent mock fallback masks backend failures | Throw errors to UI; remove silent fallbacks. |
| **FE-04** | Frontend | Missing JWT token refresh interceptor | Add 401 retry interceptor calling `/auth/refresh`. |
| **FE-05** | Frontend | Simulated ingestion & missing binary ZIP upload | Connect `AddRepositoryPage` to `POST /upload`. |
| **FE-06** | Frontend | Explorer file preview hardcoded to mock | Connect Explorer preview to real file content API. |
| **BE-01** | Backend | Startup runs `create_all` instead of Alembic | Add `alembic upgrade head` to Render build command. |
| **BE-02** | Backend | Ephemeral workspace storage on Render | Mount Render persistent disk or use object store. |
| **AI-01** | AI Provider | Embeddings fail if Ollama is unreachable | Add fallback embedding provider or health monitor. |

---

## 12. Medium-Priority Issues

Address during initial deployment stabilization:

| ID | Component | Summary | Recommended Fix |
|---|---|---|---|
| **FE-07** | Frontend | `settingsService` hardcoded to mock | Connect settings page to backend `/health` APIs. |
| **FE-08** | Frontend | Mock banners displayed in production | Remove or hide `SampleDataBanner` in production. |
| **FE-09** | Frontend | GitHub sign-in calls mock service | Wire up OAuth connect endpoint or disable button. |
| **BE-03** | Backend | Interrupted ingestion jobs stay stuck | Add lifespan startup job cleaner for stalled jobs. |
| **BE-04** | Backend | Uvicorn missing `--proxy-headers` | Add `--proxy-headers --forwarded-allow-ips='*'` to start. |
| **BE-05** | Backend | OAuth callback GET expects Bearer token | Handle redirect via frontend route. |
| **DB-02** | Database | Port 5432 vs 6543 connection mode | Standardize on Supabase Transaction Pooler URL. |
| **DB-03** | Database | No Row-Level Security (RLS) in Supabase | Enable RLS on all Supabase tables. |
| **AI-02** | AI Provider | CPU InstaBox inference latency & timeout | Increase `OLLAMA_TIMEOUT_SECONDS` to 120s. |
| **AI-03** | AI Provider | Invalid model name in `.env.example` | Fix `.env.example` to `gemini-1.5-flash`. |
| **DEP-03** | Deployment| Vercel proxy payload limit for ZIPs | Upload ZIPs directly to backend API URL. |
| **PERF-02**| Performance| Sequential embedding batch calls | Add bounded concurrency to batch embedding calls. |

---

## 13. Low-Priority Recommendations

Enhancements for operational excellence and hygiene:

| ID | Component | Summary | Recommended Fix |
|---|---|---|---|
| **BE-06** | Backend | Dual Ollama base URL env vars | Unify on `OLLAMA_BASE_URL`. |
| **BE-07** | Backend | `/api/v1/health` returns 200 on DB failure | Return HTTP 503 if DB is disconnected. |
| **DEP-01** | Deployment| Duplicate `render.yaml` in backend folder | Remove `backend/render.yaml`. |
| **DEP-04** | Deployment| Missing `.python-version` file | Create `backend/.python-version` with `3.11.9`. |
| **DEP-06** | Deployment| Obsolete Cloud Run variables in `.env.example` | Update root `.env.example` with frontend keys. |
| **FE-10** | Frontend | Large bundle chunks (>500kB) | Lazy-load heavy diagramming libraries. |
| **FE-11** | Frontend | `package.json` vestigial packages & name | Clean up `express`, rename to `repomind-frontend`. |

---

## 14. Recommended Remediation Order

To prepare RepoMind for deployment cleanly without regression:

```
Step 1: Configuration & Hygiene Cleanup (DEP-01, DEP-04, DEP-06, FE-11, AI-03, BE-06)
   └── Remove duplicate render.yaml, pin python 3.11.9, clean .env.examples and package.json.

Step 2: Backend Deployment & Startup Hardening (BE-01, BE-04, BE-06, BE-07)
   └── Add alembic upgrade head to buildCommand, add --proxy-headers to uvicorn, fix health check status codes.

Step 3: Database & Vector Search Optimization (DB-01, DB-02, DB-03)
   └── Enable pgvector extension in Supabase, create vector(768) column with HNSW index, migrate ChunkRepository.

Step 4: Frontend Authentication & Token Management (SEC-01, FE-02, FE-04)
   └── Remove default demo user from auth.store, implement 401 token refresh interceptor, transition to memory/cookie tokens.

Step 5: Frontend API Base & De-mocking (FE-01, FE-03, FE-06, FE-07, FE-08)
   └── Unify API_BASE to use VITE_API_BASE_URL, remove silent mock catch blocks, wire real Explorer and Settings endpoints.

Step 6: Real ZIP Ingestion & Upload Pipeline (FE-05, DEP-03, BE-02, BE-03)
   └── Implement multipart upload in frontend, wire AddRepositoryPage to backend, handle ephemeral storage strategy.
```

---

## 15. Phase 12.2 Implementation Checklist

The following actionable checklist is established for execution in Phase 12.2:

- [ ] **1. Deployment Blueprint & Runtime Harmonization**
  - [ ] Delete redundant `backend/render.yaml`.
  - [ ] Update root `render.yaml` `buildCommand`: `pip install -r requirements.txt && alembic upgrade head`.
  - [ ] Update root `render.yaml` `startCommand`: `uvicorn app.main:app --host 0.0.0.0 --port $PORT --proxy-headers --forwarded-allow-ips='*'`.
  - [ ] Create `backend/.python-version` containing `3.11.9`.
  - [ ] Clean root `.env.example` to define `VITE_API_BASE_URL`.
  - [ ] Clean `backend/.env.example` to fix `GEMINI_MODEL=gemini-1.5-flash`.

- [ ] **2. Frontend Authentication & State Hardening**
  - [ ] Update `src/stores/auth.store.ts`: Remove `DEFAULT_DEMO_USER` fallback in `getInitialUser()`; default to `null`.
  - [ ] Implement central fetch client `src/services/api/client.ts` supporting `VITE_API_BASE_URL`.
  - [ ] Implement automatic token refresh on 401 responses in `client.ts` using stored refresh token.
  - [ ] Remove `mockRepositoryService`, `mockAssistantService`, `mockArchitectureService`, etc., from catch blocks in `src/services/api/*.ts`.

- [ ] **3. Ingestion & File Explorer Wire-up**
  - [ ] Add `uploadRepositoryZip(file: File, name?: string)` to `src/services/api/repository.api.ts`.
  - [ ] Connect `src/features/repositories/AddRepositoryPage.tsx` to live backend upload endpoint.
  - [ ] Connect `src/services/api/explorer.api.ts:getFileIntelligence` to live backend symbols/files API.
  - [ ] Connect `src/services/index.ts:settingsService` to live backend health endpoints.
  - [ ] Remove or suppress `SampleDataBanner` mock notices in production build.

- [ ] **4. Supabase Vector Performance Enhancement**
  - [ ] Create Alembic migration to enable `pgvector` extension and add `vector(768)` column to `code_chunks`.
  - [ ] Update `ChunkRepository.search_similar_chunks` to run SQL cosine distance queries (`<=>`) in PostgreSQL.
  - [ ] Verify Supabase connection string specifies `:6543` with `ssl=require`.

- [ ] **5. Verification & Pre-flight Testing**
  - [ ] Run backend test suite: verify 153/153 tests pass.
  - [ ] Run frontend production build: verify `npm run build` succeeds cleanly.
  - [ ] Verify health endpoints `/health` and `/api/v1/health` with live database and providers.
