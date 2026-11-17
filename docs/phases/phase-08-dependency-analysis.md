# RepoMind — Phase 8: Dependency Analysis & Supabase Database Migration

## 1. Overview & Objectives

Phase 8 introduces comprehensive repository dependency intelligence and circular dependency detection, alongside migrating RepoMind's primary application database to **Supabase-managed PostgreSQL**.

### Primary Deliverables
1. **Dependency Analysis Engine**:
   - Extraction of file-level, module-level, and third-party package dependencies.
   - Module resolution for relative paths (`./`, `../`), TypeScript aliases (`@/...`), and dotted Python modules (`app.models.user`).
   - Manifest parsing (`package.json`, `requirements.txt`, etc.).
   - Isolation and reporting of unresolved imports with exact line numbers and evidence.
2. **Circular Dependency Detection**:
   - Linear-time $O(V + E)$ cycle detection via **Tarjan's Strongly Connected Components (SCC)** algorithm.
   - Canonical cycle normalization and deduplication to prevent cyclical permutation duplicates.
   - Severity scoring: `high` (spans $\ge 4$ files or cross-directory boundaries), `medium` (3 files), and `low` (2-node mutual recursion).
   - Automated architectural impact analysis and step-by-step refactoring recommendations.
3. **Interactive Frontend Dependency Explorer**:
   - ReactFlow canvas (`@xyflow/react`) featuring custom interactive dependency nodes with category-specific colors and badges.
   - Animated pulse on circular dependency edges.
   - Collapsible cycle inspector drawer with refactoring recommendations.
   - Live filters for internal files, external packages, circular dependencies, and unresolved imports.
   - Connected directly to live backend endpoints via `apiDependencyService`.
4. **Supabase Database Architecture & Migration**:
   - Primary database transitioned to Supabase-managed PostgreSQL.
   - Normalized connection URLs supporting `postgres://`, `postgresql://`, and `postgresql+asyncpg://`.
   - Production connection pool configuration with `pool_pre_ping`, `pool_recycle = 1800`, and `pool_timeout = 30`.
   - Diagnostic tool (`diagnostic.py`) and topological data migration tool (`migrate_data.py`).

---

## 2. Database Schema (Phase 8 Additions)

### `dependency_snapshots`
- `id` (VARCHAR(36), PK): UUID.
- `repository_id` (VARCHAR(36), FK -> repositories.id, UNIQUE, CASCADE).
- `graph_data_json` (TEXT): Full serialized `DependencyAnalysisData` JSON payload.
- `total_modules`, `total_imports`, `internal_count`, `external_count`, `circular_count`, `unresolved_count` (INTEGER).
- `analyzed_at` (TIMESTAMP WITH TIME ZONE).

### `code_dependencies`
- `id` (VARCHAR(36), PK): UUID.
- `repository_id` (VARCHAR(36), FK -> repositories.id, CASCADE).
- `source_file_id` (VARCHAR(36), FK -> repository_files.id, CASCADE).
- `target_file_id` (VARCHAR(36), FK -> repository_files.id, SET NULL, Nullable).
- `source_path` (VARCHAR(500)), `target_path` (VARCHAR(500), Nullable), `target_module` (VARCHAR(500)).
- `dependency_type` (VARCHAR(50)): `file`, `module`, `package`.
- `category` (VARCHAR(20)): `internal`, `external`, `unresolved`.
- `statement_type` (VARCHAR(20)): `import`, `require`, `export`.
- `imported_symbols_json` (TEXT): Serialized JSON array of identifiers.
- `line_number` (INTEGER).
- `is_circular` (BOOLEAN).
- `confidence` (VARCHAR(20)): `verified`, `inferred`.

---

## 3. Backend API Endpoints

All endpoints are authenticated with JWT and enforce repository ownership:

| Method | Endpoint | Description |
| :--- | :--- | :--- |
| `GET` | `/api/v1/repositories/{id}/dependencies/graph` | Returns the interactive dependency graph payload. |
| `POST` | `/api/v1/repositories/{id}/dependencies/analyze` | Forces complete dependency re-analysis. |
| `GET` | `/api/v1/repositories/{id}/dependencies/cycles` | Lists detected circular dependency cycles with severity and advice. |
| `GET` | `/api/v1/repositories/{id}/dependencies/direct` | Queries 1-hop upstream or downstream dependencies for a file. |
| `GET` | `/api/v1/repositories/{id}/dependencies/transitive` | Traverses BFS paths to compute transitive dependency reachability. |
| `GET` | `/api/v1/repositories/{id}/dependencies/unresolved` | Lists broken and unresolved import statements. |
| `GET` | `/api/v1/repositories/{id}/dependencies/packages` | Lists external packages and consumer file counts. |

---

## 4. Supabase Connection Configuration

In `backend/.env`:
```env
# Session Mode (Port 5432 - Recommended for Render Web Service):
DATABASE_URL=postgresql+asyncpg://postgres:[PASSWORD]@db.[PROJECT-REF].supabase.co:5432/postgres?ssl=require

# Transaction Pooler (Port 6543):
DATABASE_URL=postgresql+asyncpg://postgres.[PROJECT-REF]:[PASSWORD]@aws-0-[REGION].pooler.supabase.com:6543/postgres?ssl=require
```

### Verification CLI
```powershell
# Verify connection non-destructively:
python -m app.db.diagnostic

# Migrate data from previous database to Supabase:
python -m app.db.migrate_data --source sqlite+aiosqlite:///backend/repomind.db --target "postgresql+asyncpg://postgres:[PASSWORD]@db.[PROJECT-REF].supabase.co:5432/postgres?ssl=require"
```
