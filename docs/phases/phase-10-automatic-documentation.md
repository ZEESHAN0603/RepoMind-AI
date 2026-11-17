# Phase 10: Automatic Documentation Generation

## 1. Overview & Objective

Phase 10 delivers **Automatic Documentation Generation** for RepoMind—an automated documentation engineering engine that analyzes uploaded codebases, synthesizes structured, accurate, and editable technical documentation, persists versioned document records in Supabase PostgreSQL, and provides a rich Documentation Workspace with live Markdown editing, Mermaid diagram rendering, version diff comparison, approval workflows, and multi-format exports (.md, .html, and complete .zip packages).

Phase 10 reuses the static analysis, architecture graphs, execution call chains, dependency evaluations, and update intelligence completed in Phases 3 through 9 without re-implementing or duplicating core analysis.

---

## 2. Architecture & Components

```
┌────────────────────────────────────────────────────────────────────────┐
│                        Phase 10 Component Topology                     │
├────────────────────────────────┬───────────────────────────────────────┤
│ Component                      │ Role & Function                       │
├────────────────────────────────┼───────────────────────────────────────┤
│ `DocumentationGenerationService`│ Analyzes extracted metadata across    │
│                                │ Phases 3–9 and synthesizes 7 technical│
│                                │ sections (README, Architecture, API,  │
│                                │ Execution Flows, Dependencies, Code,  │
│                                │ and Update Changelog).                │
├────────────────────────────────┼───────────────────────────────────────┤
│ `DocumentationExportService`   │ Generates individual Markdown files,  │
│                                │ standalone HTML pages with embedded   │
│                                │ Mermaid/Marked runtimes, and streamed │
│                                │ full ZIP documentation archives.      │
├────────────────────────────────┼───────────────────────────────────────┤
│ `DocumentationRepository`      │ Manages Supabase persistence for      │
│                                │ `repository_documents` and historical │
│                                │ `repository_document_versions`.       │
├────────────────────────────────┼───────────────────────────────────────┤
│ `endpoints/documentation.py`   │ FastAPI REST endpoints for generating,│
│                                │ reading, editing, diffing, approving, │
│                                │ and exporting repository documentation│
├────────────────────────────────┼───────────────────────────────────────┤
│ `DocumentationPage.tsx`        │ Dedicated documentation workspace with│
│                                │ category sidebar, live Markdown/SVG   │
│                                │ preview, Monaco/Textarea split editor,│
│                                │ version history drawer, and export.   │
├────────────────────────────────┼───────────────────────────────────────┤
│ `apiDocumentationService`      │ Frontend API client bridging React to │
│                                │ Render FastAPI documentation routes   │
│                                │ with automatic mock fallback.         │
└────────────────────────────────┴───────────────────────────────────────┘
```

---

## 3. Database Schema Additions (Supabase PostgreSQL)

Alembic migration `d4e5f6a7b8c9_add_phase10_documentation_schema.py`:

### 1. `repository_documents`
Stores active generated documentation sections for each repository:
- `id` (VARCHAR(36), PK): UUID.
- `repository_id` (VARCHAR(36), FK -> `repositories.id` ON DELETE CASCADE, Index).
- `doc_type` (VARCHAR(50), Index): `readme`, `architecture`, `api`, `execution_flow`, `dependencies`, `update_changelog`, `code_reference`.
- `title` (VARCHAR(255)): Document title.
- `description` (TEXT): High-level section purpose.
- `content` (TEXT): Active Markdown content (compressed and stored in TOAST tables when large).
- `status` (VARCHAR(30), Index): `draft`, `approved`, `stale`, `generating`, `failed`.
- `confidence` (VARCHAR(20)): `verified`, `inferred`.
- `source_evidence_json` (TEXT): JSON citations linking to source files and line spans.
- `version_number` (INTEGER): Active revision number (starts at 1).
- `last_generated_at` (TIMESTAMP WITH TIME ZONE): Time of last static analysis run.
- `approved_at` (TIMESTAMP WITH TIME ZONE, Nullable): Timestamp of user sign-off.
- `approved_by` (VARCHAR(36), FK -> `users.id` ON DELETE SET NULL, Nullable): Approving user.
- `created_at`, `updated_at` (TIMESTAMP WITH TIME ZONE).

### 2. `repository_document_versions`
Tracks immutable historical snapshots on every manual edit or regeneration:
- `id` (VARCHAR(36), PK): UUID.
- `document_id` (VARCHAR(36), FK -> `repository_documents.id` ON DELETE CASCADE, Index).
- `repository_id` (VARCHAR(36), FK -> `repositories.id` ON DELETE CASCADE, Index).
- `version_number` (INTEGER): Sequential revision number.
- `content` (TEXT): Markdown snapshot at this revision.
- `change_summary` (VARCHAR(500), Nullable): Reason/description of revision.
- `created_by` (VARCHAR(36), FK -> `users.id` ON DELETE SET NULL, Nullable).
- `created_at` (TIMESTAMP WITH TIME ZONE).

---

## 4. Documentation Types & Grounding Rules

| Document Type | Grounded Evidence Source | Anti-Hallucination Guardrails |
| :--- | :--- | :--- |
| **README Overview** | `package.json`, `requirements.txt`, `.env.example`, `RepositoryLanguage` | Installation and run commands extracted strictly from manifests. Environment variables extracted from templates; missing elements marked `[Unknown]`. |
| **System Architecture** | `ArchitectureSnapshot` (Phase 6 graph) | Deterministic Mermaid flowchart generated directly from graph nodes and edges. Zero invented components. |
| **API Reference** | `ApiRouteEndpoint` (Phase 4 static analysis) | Extracted HTTP routes, handlers, line locations, and framework schemas. Highlights undocumented APIs. |
| **Execution Flow** | `ExecutionEntryPoint` & `CodeCall` (Phase 7) | Delineates verified static calls vs dynamic boundaries. Discloses static analysis limitations. |
| **Dependencies & Cycles** | `code_dependencies` & `DependencySnapshot` (Phase 8) | Reports Tarjan cycle analysis, package versions, and unresolved dependencies. |
| **Update Changelog** | `RepositoryUpdateRun` & `VersionSymbolChange` (Phase 9) | AST symbol mutation changelogs and blast-radius impact summaries. |
| **Code Reference** | `CodeSymbol` (Phase 4) | Functions, classes, signatures, parameters, return types, exceptions, and line-level citations. |

---

## 5. Export Formats

1. **Markdown (`.md`)**: Raw UTF-8 Markdown text streamed as attachment.
2. **Standalone HTML (`.html`)**: Self-contained HTML document with dark/light typography, embedded CSS, and runtime Mermaid/Marked rendering for offline presentation.
3. **Complete Package (`.zip`)**: Compressed ZIP archive containing all active documents and a generated `INDEX.md` manifest table of contents.
4. **PDF (`.pdf`)**: Supported via client-side `@media print` CSS and browser `window.print()` rendering.

---

## 6. Verification & Test Suite

The test suite in `backend/tests/test_phase10_documentation.py` verifies:
- `test_documentation_export_service`: Validates Markdown, HTML, and ZIP package export.
- `test_documentation_repository_operations`: Validates CRUD, auto-versioning, and approvals.
- `test_documentation_api_end_to_end`: Tests ingestion, generation, editing, version diffing, approving, and exporting via HTTP API.
- `test_documentation_security_and_multi_tenant_isolation`: Confirms multi-tenant access barriers (403 Forbidden).
