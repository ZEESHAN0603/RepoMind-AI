# RepoMind — Backend Foundation (Phase 2)

Backend foundation for **RepoMind — AI-Powered Repository Intelligence Platform**.

## Architecture & Technology Stack
- **Language**: Python 3.11
- **Framework**: FastAPI (Async, Layered, Clean Architecture)
- **ASGI Server**: Uvicorn
- **Database ORM**: SQLAlchemy 2.x (Async Engine & Sessionmaker)
- **Database Engine**: Supabase-managed PostgreSQL (Sole Application Database)
- **Database Driver**: `asyncpg` (PostgreSQL / Supabase with SSL & connection pooling)
- **Database Migrations**: Alembic
- **Authentication**: JWT access & refresh tokens with Argon2 password hashing
- **Validation & Settings**: Pydantic v2 & Pydantic-Settings
- **Testing**: Pytest, pytest-asyncio, HTTPX

---

## Directory Structure

```text
backend/
├── app/
│   ├── main.py                         # Application entrypoint & lifespan
│   ├── ai/                             # AI & LLM Provider Abstraction (Phase 5)
│   │   ├── base.py                     # BaseLLMProvider interface
│   │   ├── ollama_provider.py          # InstaBox Ollama client (qwen3.5:4b, nomic-embed-text)
│   │   ├── gemini_provider.py          # Gemini Free-Tier fallback client
│   │   ├── provider_manager.py         # Dual-provider router & secret sanitizer
│   │   ├── schemas.py                  # AI dataclasses (ChatMessage, GenerationResult, etc.)
│   │   └── exceptions.py               # Categorized provider exceptions
│   ├── core/
│   │   ├── config.py                   # Centralized Pydantic Settings
│   │   ├── security.py                 # Argon2 hashing & JWT lifecycle
│   │   ├── logging.py                  # Structured console logging
│   │   ├── exceptions.py               # Custom domain exceptions
│   │   ├── middleware.py               # Correlation ID & request logger
│   │   └── error_handlers.py           # Centralized exception handlers
│   ├── api/
│   │   └── v1/
│   │       ├── router.py               # API v1 centralized router
│   │       ├── dependencies.py         # JWT auth & get_current_user
│   │       └── endpoints/
│   │           ├── health.py           # Health checks
│   │           ├── auth.py             # Register, login, refresh, logout, me
│   │           ├── users.py            # User profile management
│   │           └── repositories.py     # Repository management
│   ├── models/
│   │   ├── user.py                     # User model
│   │   ├── repository.py               # Repository model
│   │   └── token.py                    # RefreshToken model
│   ├── schemas/
│   │   ├── user.py                     # User schemas
│   │   ├── token.py                    # Token & response schemas
│   │   └── repository.py               # Repository schemas
│   ├── services/
│   │   ├── auth_service.py             # Auth & token rotation logic
│   │   └── user_service.py             # User profile logic
│   ├── repositories/
│   │   ├── user_repository.py          # User queries
│   │   ├── token_repository.py         # Refresh token revocation queries
│   │   └── repository_repository.py    # Repository queries
│   └── db/
│       ├── base.py                     # Base & TimestampMixin
│       └── session.py                  # Engine & get_db dependency
├── migrations/                         # Alembic migration scripts
├── tests/                              # Pytest test suite (21 passing tests)
├── .env.example
├── .gitignore
├── alembic.ini
├── pytest.ini
├── requirements.txt
└── README.md
```

---

## Windows PowerShell Quickstart

```powershell
# Navigate to backend directory
cd "D:\RepoMind AI\backend"

# Activate virtual environment
.\.venv\Scripts\Activate.ps1

# Run database migrations
alembic upgrade head

# Run development server
uvicorn app.main:app --reload --host 127.0.0.1 --port 8000
```

---

## Running Automated Tests

```powershell
cd "D:\RepoMind AI\backend"
.\.venv\Scripts\pytest.exe -v
```

---

## API Endpoints (v1)

### Health
- `GET /` — Application information
- `GET /health` — Service health
- `GET /api/v1/health` — API v1 and database health status

### Authentication (`/api/v1/auth`)
- `POST /api/v1/auth/register` — Register account (Argon2 hash, email duplicate check)
- `POST /api/v1/auth/login` — Authenticate and receive access & refresh tokens
- `POST /api/v1/auth/refresh` — Refresh access token (with token rotation)
- `POST /api/v1/auth/logout` — Revoke refresh token
- `GET  /api/v1/auth/me` — Authenticated user details

### Users (`/api/v1/users`)
- `GET    /api/v1/users/me` — Fetch user profile
- `PATCH  /api/v1/users/me` — Update name or email
- `DELETE /api/v1/users/me` — Delete account

### Repositories (`/api/v1/repositories`)
- `GET    /api/v1/repositories` — List user's repositories
- `POST   /api/v1/repositories` — Connect repository
- `GET    /api/v1/repositories/{id}` — Get repository details
- `DELETE /api/v1/repositories/{id}` — Disconnect repository

### Execution Flow Tracing (`/api/v1/repositories/{id}/execution`)
- `POST   /api/v1/repositories/{id}/execution/analyze` — Trigger call extraction, resolution, and trace generation
- `GET    /api/v1/repositories/{id}/execution/workspace` — Full execution workspace (traces, nodes, edges, function symbols)
- `GET    /api/v1/repositories/{id}/execution/entry-points` — List discovered application entry points
- `GET    /api/v1/repositories/{id}/execution/nodes/{symbol_id}/calls` — Get incoming callers and outgoing callees for a symbol
- `GET    /api/v1/repositories/{id}/execution/trace-path` — Find path between source and target symbols
- `POST   /api/v1/repositories/{id}/execution/explain` — AI-grounded flow explanation with verified steps and uncertainties

### Repository Update Intelligence (`/api/v1/repositories/{id}/updates`)
- `GET    /api/v1/repositories/{id}/updates/history` — List update runs, versions, and sync status
- `POST   /api/v1/repositories/{id}/updates/analyze` — Trigger update analysis between base and target versions
- `GET    /api/v1/repositories/{id}/updates/{update_run_id}` — Get full update report (stats, blast radius, diffs)
- `GET    /api/v1/repositories/{id}/updates/{update_run_id}/files` — List changed files with category and line stats
- `GET    /api/v1/repositories/{id}/updates/{update_run_id}/symbols` — List changed symbols with signature diffs and evidence
- `GET    /api/v1/repositories/{id}/updates/{update_run_id}/impact` — List blast radius impact records
- `GET    /api/v1/repositories/{id}/updates/{update_run_id}/graph` — Get blast radius impact sub-graph
- `POST   /api/v1/repositories/{id}/updates/{update_run_id}/explain` — Generate grounded AI change summary
- `POST   /api/v1/repositories/{id}/updates/compare` — Ad-hoc commit or snapshot comparison
