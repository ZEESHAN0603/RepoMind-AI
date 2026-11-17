# RepoMind — Database Schema

## 1. Schema & Database Architecture Overview

RepoMind employs a normalized relational database schema managed via **SQLAlchemy 2.0 (Async)** and **Alembic**, backed exclusively by **Supabase-managed PostgreSQL** as the sole primary application database provider.

### Supabase Connection Topology
- **Primary Relational Engine**: Supabase-managed PostgreSQL 15+.
- **Session Mode (Direct on Port 5432 - Recommended for Render)**:
  `postgresql+asyncpg://postgres:[PASSWORD]@db.[PROJECT-REF].supabase.co:5432/postgres?ssl=require`
- **Transaction Pooler (Supavisor on Port 6543)**:
  `postgresql+asyncpg://postgres.[PROJECT-REF]:[PASSWORD]@aws-0-[REGION].pooler.supabase.com:6543/postgres?ssl=require`
  *(Statement caching disabled via `statement_cache_size=0` for transaction-pooled connections)*
- **Driver**: `asyncpg` with automated TLS 1.3 encryption and connection pre-ping (`pool_pre_ping=True`).
- **Isolation & Security**: Privileged database access is restricted entirely to the FastAPI backend hosted on Render. The React frontend on Vercel never accesses the database directly or holds service-role credentials.

```mermaid
erDiagram
    users ||--o{ repositories : owns
    users ||--o{ refresh_tokens : has
    repositories ||--o{ repository_files : contains
    repositories ||--o{ repository_languages : detects
    repositories ||--o{ repository_manifests : parses
    repositories ||--o{ ingestion_jobs : tracks
    repositories ||--o{ code_symbols : defines
    repositories ||--o{ code_imports_exports : declares
    repositories ||--o{ api_route_endpoints : exposes
    repositories ||--o{ code_chunks : embeds
    repositories ||--o{ chat_conversations : conducts
    repositories ||--o| architecture_snapshots : caches
    repositories ||--o{ code_calls : records
    repositories ||--o{ execution_entry_points : registers
    repositories ||--o| execution_snapshots : caches
    repositories ||--o| dependency_snapshots : caches
    repositories ||--o{ code_dependencies : tracks
    repositories ||--o{ repository_versions : records
    repositories ||--o{ repository_update_runs : executes
    repository_update_runs ||--o{ version_file_changes : contains
    repository_update_runs ||--o{ version_symbol_changes : contains
    repository_update_runs ||--o{ version_impact_records : tracks
    repositories ||--o{ repository_documents : has
    repository_documents ||--o{ repository_document_versions : tracks
    chat_conversations ||--o{ chat_messages : records
```

## 2. Table Specifications

### `repositories`
- `id` (VARCHAR(36), PK): UUID.
- `owner_id` (VARCHAR(36), FK -> users.id).
- `name` (VARCHAR(255)), `owner` (VARCHAR(255)), `repository_url` (VARCHAR(500)).
- `default_branch`, `current_commit_sha`, `visibility`, `status`.
- `file_count`, `folder_count`, `last_analyzed_at`.

### `code_symbols`
- `id` (VARCHAR(36), PK).
- `repository_id` (VARCHAR(36), FK -> repositories.id).
- `file_id` (VARCHAR(36), FK -> repository_files.id).
- `name`, `symbol_type` (function, method, class, interface, enum, struct).
- `start_line`, `end_line`, `signature`, `docstring`, `parameters`, `return_type`.
- `is_async`, `is_exported`, `visibility`, `confidence`.

### `code_imports_exports`
- `id` (VARCHAR(36), PK).
- `repository_id` (VARCHAR(36), FK -> repositories.id).
- `file_id` (VARCHAR(36), FK -> repository_files.id).
- `statement_type` ("import" or "export").
- `source_module` (VARCHAR(500)), `symbol_name`, `alias`, `is_relative`, `line_number`.

### `api_route_endpoints`
- `id` (VARCHAR(36), PK).
- `repository_id` (VARCHAR(36), FK -> repositories.id).
- `file_id` (VARCHAR(36), FK -> repository_files.id).
- `http_method` (GET, POST, etc.), `path`, `handler_name`, `framework`, line numbers.

### `architecture_snapshots` *(New in Phase 6)*
- `id` (VARCHAR(36), PK).
- `repository_id` (VARCHAR(36), FK -> repositories.id, UNIQUE).
- `graph_data_json` (TEXT): Full serialized `ArchitectureGraphData` JSON payload.
- `node_count` (INTEGER), `edge_count` (INTEGER).
- `analyzed_at` (TIMESTAMP WITH TIME ZONE).

### `code_calls` *(New in Phase 7)*
- `id` (VARCHAR(36), PK).
- `repository_id` (VARCHAR(36), FK -> repositories.id).
- `file_id` (VARCHAR(36), FK -> repository_files.id).
- `caller_symbol_id` (VARCHAR(36), FK -> code_symbols.id, Nullable).
- `callee_symbol_id` (VARCHAR(36), FK -> code_symbols.id, Nullable).
- `caller_symbol_name` (VARCHAR(255)).
- `callee_name` (VARCHAR(255)).
- `call_type` (VARCHAR(50)): `function`, `method`, `api`, `external`, `database`.
- `resolution_status` (VARCHAR(50)): `verified`, `inferred`, `unresolved`, `external`.
- `line_number`, `end_line_number` (INTEGER).
- `call_snippet` (TEXT).
- `confidence` (VARCHAR(50)): `high`, `medium`, `low`.

### `execution_entry_points` *(New in Phase 7)*
- `id` (VARCHAR(36), PK).
- `repository_id` (VARCHAR(36), FK -> repositories.id).
- `file_id` (VARCHAR(36), FK -> repository_files.id).
- `symbol_id` (VARCHAR(36), FK -> code_symbols.id, Nullable).
- `name` (VARCHAR(255)).
- `entry_point_type` (VARCHAR(50)): `api-endpoint`, `startup-file`, `main-function`, `cli-command`, `background-job`, `ui-event`.
- `file_path` (VARCHAR(1000)).
- `line_number` (INTEGER).
- `http_method` (VARCHAR(20), Nullable).
- `route_path` (VARCHAR(500), Nullable).
- `is_verified` (BOOLEAN).
- `description` (TEXT, Nullable).

### `execution_snapshots` *(New in Phase 7)*
- `id` (VARCHAR(36), PK).
- `repository_id` (VARCHAR(36), FK -> repositories.id, UNIQUE).
- `workspace_data_json` (TEXT): Full serialized `ExecutionWorkspaceResponse` JSON payload.
- `trace_count` (INTEGER).
- `function_count` (INTEGER).
- `analyzed_at` (TIMESTAMP WITH TIME ZONE).

### `dependency_snapshots` *(New in Phase 8)*
- `id` (VARCHAR(36), PK).
- `repository_id` (VARCHAR(36), FK -> repositories.id, UNIQUE).
- `graph_data_json` (TEXT): Full serialized `DependencyAnalysisData` JSON payload.
- `total_modules` (INTEGER), `total_imports` (INTEGER).
- `internal_count` (INTEGER), `external_count` (INTEGER).
- `circular_count` (INTEGER), `unresolved_count` (INTEGER).
- `analyzed_at` (TIMESTAMP WITH TIME ZONE).

### `code_dependencies` *(New in Phase 8)*
- `id` (VARCHAR(36), PK).
- `repository_id` (VARCHAR(36), FK -> repositories.id).
- `source_file_id` (VARCHAR(36), FK -> repository_files.id).
- `target_file_id` (VARCHAR(36), FK -> repository_files.id, Nullable).
- `source_path` (VARCHAR(500)), `target_path` (VARCHAR(500), Nullable), `target_module` (VARCHAR(500)).
- `dependency_type` (VARCHAR(50)): `file`, `module`, `package`.
- `category` (VARCHAR(20)): `internal`, `external`, `unresolved`.
- `statement_type` (VARCHAR(20)): `import`, `require`, `export`.
- `imported_symbols_json` (TEXT): JSON array of imported identifiers.
- `line_number` (INTEGER).
- `is_circular` (BOOLEAN).
- `confidence` (VARCHAR(20)): `verified`, `inferred`.

### `repository_versions` *(New in Phase 9)*
- `id` (VARCHAR(36), PK): UUID.
- `repository_id` (VARCHAR(36), FK -> repositories.id ON DELETE CASCADE).
- `version_tag` (VARCHAR(100)): Tag or human-readable identifier (e.g. `commit:9a4f21c` or `snapshot:v1`).
- `commit_sha` (VARCHAR(64), Nullable): 40-character Git commit hash (NULL for ZIP snapshots).
- `commit_message` (TEXT, Nullable).
- `author_name` (VARCHAR(150)), `author_email` (VARCHAR(255)).
- `commit_timestamp` (TIMESTAMP WITH TIME ZONE, Nullable).
- `source_type` (VARCHAR(50)): `github_commit`, `zip_snapshot`.

### `repository_update_runs` *(New in Phase 9)*
- `id` (VARCHAR(36), PK): UUID.
- `repository_id` (VARCHAR(36), FK -> repositories.id ON DELETE CASCADE).
- `base_version_id` (VARCHAR(36), FK -> repository_versions.id, Nullable).
- `target_version_id` (VARCHAR(36), FK -> repository_versions.id ON DELETE CASCADE).
- `base_commit_sha` (VARCHAR(64), Nullable), `target_commit_sha` (VARCHAR(64), Nullable).
- `status` (VARCHAR(30)): `queued`, `analyzing`, `completed`, `failed`.
- `total_files_changed`, `total_symbols_changed`, `total_additions`, `total_deletions` (INTEGER).
- `impact_summary_json` (TEXT): JSON metrics of blast radius classifications.
- `ai_summary_markdown` (TEXT, Nullable): Grounded AI change explanation.
- `ai_summary_status` (VARCHAR(30)): `pending`, `generating`, `completed`, `failed`.
- `analyzed_at` (TIMESTAMP WITH TIME ZONE).

### `version_file_changes` *(New in Phase 9)*
- `id` (VARCHAR(36), PK): UUID.
- `update_run_id` (VARCHAR(36), FK -> repository_update_runs.id ON DELETE CASCADE).
- `path` (VARCHAR(1000)), `old_path` (VARCHAR(1000), Nullable).
- `change_type` (VARCHAR(20)): `added`, `modified`, `deleted`, `renamed`.
- `file_category` (VARCHAR(30)): `source`, `config`, `manifest`, `documentation`, `other`.
- `additions`, `deletions` (INTEGER).
- `old_size_bytes`, `new_size_bytes` (BIGINT).
- `old_content_hash`, `new_content_hash` (VARCHAR(64)).
- `diff_patch` (TEXT): Unified diff patch string (bounded to 200 KB).
- `summary` (TEXT).

### `version_symbol_changes` *(New in Phase 9)*
- `id` (VARCHAR(36), PK): UUID.
- `update_run_id` (VARCHAR(36), FK -> repository_update_runs.id ON DELETE CASCADE).
- `file_change_id` (VARCHAR(36), FK -> version_file_changes.id ON DELETE CASCADE, Nullable).
- `symbol_name` (VARCHAR(255)), `symbol_type` (VARCHAR(50)), `scope` (VARCHAR(255), Nullable).
- `change_type` (VARCHAR(20)): `added`, `modified`, `deleted`, `renamed`.
- `old_signature` (TEXT, Nullable), `new_signature` (TEXT, Nullable).
- `evidence_json` (TEXT): Structured diff rationale and parameter/body changes.

### `version_impact_records` *(New in Phase 9)*
- `id` (VARCHAR(36), PK): UUID.
- `update_run_id` (VARCHAR(36), FK -> repository_update_runs.id ON DELETE CASCADE).
- `affected_type` (VARCHAR(50)): `file`, `symbol`, `caller`, `endpoint`, `architecture_component`.
- `affected_identifier` (VARCHAR(500)), `affected_path` (VARCHAR(1000)).
- `impact_level` (VARCHAR(30)): `directly_changed`, `directly_affected`, `indirectly_affected`, `potentially_affected`, `unknown`.
- `evidence_reason` (TEXT): Graph traversal reason justifying blast radius placement.
- `source_change_symbol_id` (VARCHAR(36), FK -> version_symbol_changes.id, Nullable).
- `depth` (INTEGER): Traversal hop distance from directly changed node.

### `repository_documents` *(New in Phase 10)*
- `id` (VARCHAR(36), PK): UUID.
- `repository_id` (VARCHAR(36), FK -> repositories.id ON DELETE CASCADE).
- `doc_type` (VARCHAR(50)): `readme`, `architecture`, `api`, `execution_flow`, `dependencies`, `update_changelog`, `code_reference`.
- `title` (VARCHAR(255)), `description` (TEXT), `content` (TEXT).
- `status` (VARCHAR(30)): `draft`, `approved`, `stale`, `generating`, `failed`.
- `confidence` (VARCHAR(20)): `verified`, `inferred`.
- `source_evidence_json` (TEXT): Sourced file/line citation map.
- `version_number` (INTEGER, Default 1).
- `last_generated_at` (TIMESTAMP WITH TIME ZONE).
- `approved_at` (TIMESTAMP WITH TIME ZONE, Nullable), `approved_by` (VARCHAR(36), FK -> users.id, Nullable).

### `repository_document_versions` *(New in Phase 10)*
- `id` (VARCHAR(36), PK): UUID.
- `document_id` (VARCHAR(36), FK -> repository_documents.id ON DELETE CASCADE).
- `repository_id` (VARCHAR(36), FK -> repositories.id ON DELETE CASCADE).
- `version_number` (INTEGER).
- `content` (TEXT): Historical Markdown snapshot.
- `change_summary` (VARCHAR(500), Nullable).
- `created_by` (VARCHAR(36), FK -> users.id, Nullable).
- `created_at` (TIMESTAMP WITH TIME ZONE).

