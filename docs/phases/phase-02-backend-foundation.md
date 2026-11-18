# Phase 2: Backend Foundation & API Architecture

## Status: Completed

### Scope & Invariants
- **Framework**: FastAPI (Python 3.11+) with asynchronous execution.
- **Database**: Supabase-managed PostgreSQL with AsyncSQLAlchemy 2.0 and asyncpg driver.
- **ORM / Models**: Fully typed declarative models with UUID primary keys and tenant isolation foreign keys.
- **Authentication**: JWT authentication with Argon2 password hashing, access token expiration (30-60 min), and refresh token rotation (7 days).
- **Validation**: Strict Pydantic v2 schemas for all request payloads and response envelopes.
- **Error Handling**: Centralized exception handler mapping domain exceptions (`NotFoundException`, `ConflictException`, `BadRequestException`, `UnauthorizedException`) to standardized JSON error envelopes with request correlation IDs.
- **Security & Observability**: Correlation ID middleware, structured logging, CORS enforcement, and request rate limiting (`slowapi`).

---

### Architecture & Components

#### 1. Application Core (`app/core`)
- `config.py`: Environment variable validation via `pydantic-settings` with default fallbacks.
- `security.py`: Argon2 password hashing, JWT encoding/decoding, and token lifecycle management.
- `exceptions.py` & `error_handlers.py`: Hierarchy of HTTP exceptions and centralized FastAPI handlers returning `{ "error": { "code": "...", "message": "...", "correlation_id": "..." } }`.
- `middleware.py`: `RequestCorrelationMiddleware` attaching `X-Correlation-ID` to all requests and responses.
- `limiter.py`: `slowapi` rate limiter based on client remote address.

#### 2. Database Layer (`app/db` & `app/models`)
- `base.py`: SQLAlchemy `DeclarativeBase` metadata registry.
- `session.py`: Async engine factory supporting Supabase direct connections, Supabase Transaction Pooler (Supavisor on port 6543 with disabled statement caching), and isolated in-memory SQLite for testing.
- `models/`: Declarative models for `User`, `Repository`, `RepositoryFile`, `CodeSymbol`, `SymbolReference`, `ArchitectureSnapshot`, `ExecutionEntryPoint`, `CodeCall`, `DependencyNode`, `DependencyEdge`, `UpdateAnalysis`, `DocumentationDocument`.

#### 3. API Routing (`app/api/v1`)
- `/auth`: Registration, login, token refresh, logout, and current user profile (`/me`).
- `/repositories`: CRUD operations for user repositories and status checks.
- `/repositories/{id}/files`: File tree navigation and content retrieval.
- `/repositories/{id}/symbols`: Extracted symbol queries and cross-file references.
- `/repositories/{id}/architecture`: Architecture graphs and module relationship endpoints.
- `/repositories/{id}/execution`: Entry points and call chains.
- `/repositories/{id}/dependencies`: Direct, transitive, circular, and package dependencies.
- `/repositories/{id}/updates`: Snapshot comparisons, file diffs, and change impact.
- `/repositories/{id}/documentation`: Document generation, editing, status management, and exports.
- `/repositories/{id}/chat`: RAG conversation management and question answering.
