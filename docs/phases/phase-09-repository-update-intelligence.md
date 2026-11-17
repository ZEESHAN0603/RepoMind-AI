# Phase 9: Repository Update Intelligence

## 1. Overview & Objective

Phase 9 delivers **Repository Update Intelligence** for RepoMind—an automated system that detects code and file changes across repository versions/commits, tracks AST symbol mutations with line-shift invariance, computes multi-level blast-radius impact analysis across call and dependency graphs, persists historical update runs in Supabase PostgreSQL, generates grounded AI change summaries, and renders an interactive update intelligence dashboard.

---

## 2. Architecture & Components

```
┌────────────────────────────────────────────────────────────────────────┐
│                        Phase 9 Component Topology                      │
├────────────────────────────────┬───────────────────────────────────────┤
│ Component                      │ Role & Function                       │
├────────────────────────────────┼───────────────────────────────────────┤
│ `UpdateDetectionService`       │ Compares file sets, categorizes files │
│                                │ (source/config/manifest/docs), detects│
│                                │ renames, computes additions/deletions │
│                                │ and memory-capped unified diffs.      │
├────────────────────────────────┼───────────────────────────────────────┤
│ `SymbolDiffService`            │ AST symbol diffing with strict line-  │
│                                │ shift invariance; detects signature,  │
│                                │ parameter, return type, decorator, and│
│                                │ body modifications; detects endpoint  │
│                                │ handler changes.                      │
├────────────────────────────────┼───────────────────────────────────────┤
│ `ImpactAnalysisService`        │ Traverses Phase 6 (Architecture),     │
│                                │ Phase 7 (Call Graph), and Phase 8     │
│                                │ (Dependency Graph) to calculate blast │
│                                │ radius: directly changed, directly    │
│                                │ affected, transitively affected, and  │
│                                │ potentially affected elements.        │
├────────────────────────────────┼───────────────────────────────────────┤
│ `AIChangeSummaryService`       │ Builds hallucination-resistant prompts│
│                                │ from verified diff evidence, enforces │
│                                │ `REDACTION_RULES` for secrets, and    │
│                                │ calls `ProviderManager` (Ollama/      │
│                                │ Gemini fallback).                     │
├────────────────────────────────┼───────────────────────────────────────┤
│ `UpdateService`                │ Central orchestrator coordinating     │
│                                │ version comparison, diff extraction,  │
│                                │ impact computation, and persistence.  │
├────────────────────────────────┼───────────────────────────────────────┤
│ `UpdateRepository`             │ Supabase database operations for      │
│                                │ versions, update runs, file changes,  │
│                                │ symbol changes, and impact records.   │
├────────────────────────────────┼───────────────────────────────────────┤
│ `UpdatesPage.tsx`              │ Interactive React dashboard with      │
│                                │ timeline, sync status, file explorer, │
│                                │ symbol explorer, impact matrix, and   │
│                                │ AI explanation report.                │
└────────────────────────────────┴───────────────────────────────────────┘
```

---

## 3. Database Schema Additions (Supabase PostgreSQL)

Alembic migration `c3d4e5f6a7b8_add_phase9_repository_updates_schema.py`:

1. `repository_versions`:
   - Tracks historical commits and uploaded snapshots (`version_tag`, `commit_sha`, `commit_message`, `author_name`, `author_email`, `commit_timestamp`, `source_type`).
2. `repository_update_runs`:
   - Records comparison runs (`base_version_id`, `target_version_id`, `total_files_changed`, `total_symbols_changed`, `total_additions`, `total_deletions`, `impact_summary_json`, `ai_summary_markdown`, `ai_summary_status`).
3. `version_file_changes`:
   - File-level diff records (`path`, `old_path`, `change_type`, `file_category`, `additions`, `deletions`, `diff_patch`, `summary`).
4. `version_symbol_changes`:
   - Code symbol mutations (`symbol_name`, `symbol_type`, `scope`, `change_type`, `old_signature`, `new_signature`, `evidence_json`).
5. `version_impact_records`:
   - Blast radius dependents (`affected_type`, `affected_identifier`, `affected_path`, `impact_level`, `evidence_reason`, `depth`).

---

## 4. REST API Contracts

All endpoints live under `/api/v1/repositories/{id}/updates`:

- `GET /history`: Returns timeline of update runs, versions, and sync status.
- `POST /analyze`: Triggers update analysis between base and target.
- `GET /{run_id}`: Retrieves comprehensive update report with stats and impact metrics.
- `GET /{run_id}/files`: Lists changed files with optional `change_type` filter.
- `GET /{run_id}/symbols`: Lists changed symbols with signatures and evidence.
- `GET /{run_id}/impact`: Lists blast radius impact records.
- `GET /{run_id}/graph`: Returns graph nodes and edges for blast radius visualization.
- `POST /{run_id}/explain`: Generates or re-generates AI change explanation.
- `POST /compare`: Ad-hoc commit/snapshot comparison.

---

## 5. Blast-Radius Classification

1. **Directly Changed**: Files and symbols with verified content/signature diffs.
2. **Directly Affected**:
   - Direct callers of modified functions (Phase 7 `CodeCall`).
   - Modules directly importing modified files (Phase 8 `CodeDependency`).
   - Endpoints handled by modified functions (Phase 4 `ApiRouteEndpoint`).
3. **Indirectly Affected**:
   - Transitive callers via BFS on `CodeCall`.
   - Transitive dependents via BFS on `CodeDependency`.
   - Architecture components containing affected files (Phase 6).
4. **Potentially Affected**:
   - Dynamic or unresolved calls matching symbol names.
   - Frontend consumers matching modified routes.
5. **Unknown Impact**:
   - Unresolved third-party packages or dynamic imports.

---

## 6. Verification & Test Suite

- **Unit Tests:** `backend/tests/test_phase9_update_intelligence.py`
  - File categorization & rename detection
  - Line-shift invariance verification
  - Signature and body AST modification extraction
  - Secret scrubbing (`REDACTION_RULES`) and grounded fallback
- **Integration Tests:** `backend/tests/test_phase9_api.py`
  - End-to-end repository creation, update analysis, run detail retrieval, files, symbols, impact records, graph, and authorization checks.
- **Suite Result:** 139 passing tests (100% pass rate) with zero regressions across Phases 1–8.
