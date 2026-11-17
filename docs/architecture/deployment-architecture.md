# Deployment Architecture

## 1. Global Infrastructure Topology

RepoMind distributes its workloads across specialized environments to maintain low latency, data isolation, and cost control:

```text
┌─────────────────────────┐
│     Vercel (Frontend)   │
│  React 19 + Vite + SPA  │
└────────────┬────────────┘
             │ HTTPS (JWT Auth)
             ▼
┌─────────────────────────┐
│   Render (FastAPI API)  │
│ Python 3.11 + SQLAlchemy│
└──────┬────────────┬─────┘
       │            │
       │ (HTTPS)    │ (HTTPS + Token Auth)
       ▼            ▼
┌──────────────┐  ┌──────────────────────────────────────────────────┐
│   Supabase   │  │   InstaBox (Ollama Dedicated Model Server)       │
│  PostgreSQL  │  │   https://11434-agq6j3olyzqnjz6i3vl5zgyvj4...    │
└──────────────┘  │   - qwen3.5:4b (Chat Inference)                  │
                  │   - nomic-embed-text (Embeddings)                │
                  │   - Private Port Auth: Authorization: Bearer     │
                  └──────────────────────────────────────────────────┘
                            │ (Recoverable Failover)
                            ▼
                  ┌───────────────────────────────────┐
                  │ Google Gemini API (Free Tier Only)│
                  │ - gemini-1.5-flash Fallback       │
                  └───────────────────────────────────┘
```

## 2. Component Hosting Breakdown

| Component | Target Platform | Environment / Specifications | Communication Security |
| :--- | :--- | :--- | :--- |
| **Frontend UI** | Vercel | Node 20 / Edge CDN, Static SPA | TLS 1.3, zero server secrets exposed |
| **Backend API** | Render | Web Service (Python 3.11, Uvicorn) | TLS 1.3, holds all JWT & AI secrets |
| **Primary AI Server** | InstaBox | Cloud Linux VM (4 vCPU, 8 GB RAM) | HTTPS over port 11434 with private port token |
| **Fallback AI** | Google Cloud | Gemini Free Tier REST API | HTTPS with backend `GEMINI_API_KEY` |
| **Relational Database** | Supabase | Managed PostgreSQL 15+ (Direct / Session Mode on 5432) | TLS 1.3, SSL connection pooling, statement caching disabled on transaction pooler |

## 3. InstaBox Private Port Configuration

InstaBox secures exposed VM ports using a private port gateway:

- **Host Base URL**: `https://11434-agq6j3olyzqnjz6i3vl5zgyvj4.instabox.tech`
- **Authentication**: Private port token (prefixed with `ibp_`)
- **Protocol Contract**:
  - Sent programmatically via `Authorization: Bearer <OLLAMA_ACCESS_TOKEN>` header.
  - Also supported via URL query parameter `?_token=<OLLAMA_ACCESS_TOKEN>`.
  - Unauthorized requests receive HTTP 401 or HTTP 403 and **will not wake up a paused machine**.
- **Cold-Start Handling**:
  - The InstaBox free-tier machine may enter an idle pause.
  - Backend uses a 10s connection timeout and 60s read timeout.
  - When paused, connection requests may block until the machine resumes; if uncontactable, backend classifies it as `CONNECTION_ERROR` and initiates sanitized fallback to Gemini if enabled.
