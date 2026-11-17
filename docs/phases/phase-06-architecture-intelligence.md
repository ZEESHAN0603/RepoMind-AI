# Phase 6: Architecture Intelligence

## 1. Overview & Objective

Phase 6 introduces **Architecture Intelligence** to RepoMind, transforming raw repository source code, AST-extracted symbols, and static imports into interactive, multi-view architectural dependency graphs.

The Architecture Intelligence engine establishes:
- High-level system topology and layer boundaries.
- Precise multi-language module and path resolution (Python dotted/relative imports and TypeScript/JavaScript path aliases and index exports).
- Verifiable architectural relationships with strict confidence levels (`verified` vs `inferred`).
- Multi-view graph slicing (`system`, `frontend`, `backend`, `api`, `database`, `modules`).
- Non-overlapping hierarchical 2D layout coordinates for responsive rendering in `@xyflow/react`.
- Sub-50ms graph caching via the `architecture_snapshots` database entity.

---

## 2. Core Components Implemented

### 2.1 Module & Path Resolution Engine (`app.analysis.module_resolver.ModuleResolver`)
- Resolves cross-file static imports across Python, JavaScript, and TypeScript.
- Handles Python relative dot syntax (`.`, `..`), package roots (`backend`, `src`, `app`), and module `__init__.py` files.
- Handles TypeScript `@/*` path aliases, relative paths (`./`, `../`), and extension variations (`.ts`, `.tsx`, `.js`, `/index.ts`).
- Identifies external third-party dependencies (e.g., `fastapi`, `react`, `sqlalchemy`) and prevents false internal resolutions.

### 2.2 Architectural Layer Classifier (`app.services.architecture_classifier.ArchitectureClassifier`)
- Classifies files and modules into the 10 canonical architectural categories:
  - `frontend`: React/Vite pages, components, views, and state management stores.
  - `backend`: Domain services, handlers, and business logic modules.
  - `api`: FastAPI/Flask/Express route endpoints and HTTP controllers.
  - `database`: ORM entities, database models, schemas, and migrations.
  - `authentication`: Security services, JWT tokens, and auth controllers.
  - `ai`: LLM providers, vector chunking, and RAG pipelines.
  - `worker`: Background tasks, queues, and indexing workers.
  - `utility`: Shared utilities, helpers, formatters, and types.
  - `external`: Third-party integration clients and libraries.
  - `internal`: Internal core subsystems.

### 2.3 Architecture Graph Builder (`app.services.architecture_graph_builder.ArchitectureGraphBuilder`)
- Connects file-level nodes using verified AST imports and API routes.
- Statically links frontend API client calls to backend endpoint routes (`calls GET /api/v1/...`).
- Calculates non-overlapping 2D layout coordinates (`x`, `y`) by topological layer column.
- Slices the unified graph into 6 dedicated architectural views:
  1. `system`: Overall system architecture and subsystem boundaries.
  2. `frontend`: Frontend UI tree, pages, components, and state stores.
  3. `backend`: Routers, services, repositories, and AI services.
  4. `api`: API endpoints and frontend client integrations.
  5. `database`: Relational models, schemas, and service-to-database links.
  6. `modules`: Comprehensive file and package import dependency topology.

### 2.4 Snapshot Persistence & Cache (`app.models.architecture_snapshot.ArchitectureSnapshot`)
- Stores precomputed graph structures in SQLite/PostgreSQL to guarantee instant load times.
- Automatically refreshes when new static analysis runs or on demand via `force_refresh=True`.

---

## 3. API Endpoints

All endpoints are secured and require repository ownership:

| HTTP Method | Route | Description |
| :--- | :--- | :--- |
| `GET` | `/api/v1/repositories/{id}/architecture/graph` | Returns unified architecture graph with all 6 view payloads. |
| `GET` | `/api/v1/repositories/{id}/architecture/views/{view_mode}` | Returns a single view mode slice (`system`, `frontend`, etc.). |
| `GET` | `/api/v1/repositories/{id}/architecture/nodes/{node_id}` | Returns node details, incoming/outgoing relationships, and exports. |

---

## 4. Frontend Integration

- `src/services/api/architecture.api.ts`: Real `ApiArchitectureService` wired to `/api/v1/repositories/{id}/architecture/graph`.
- Automatic fallback to sample data for unauthenticated or offline demo environments (`repo-cloud-gateway`).
- `ArchitecturePage.tsx`: Interactive React Flow canvas with custom nodes, category color coding, confidence badges, minimap, zoom/pan controls, search, and node inspection drawer.

---

## 5. Verification & Test Coverage

All Phase 6 components are backed by rigorous automated unit and integration tests:
- `backend/tests/test_module_resolver.py`: Tests relative/absolute Python and TypeScript module resolution.
- `backend/tests/test_architecture_classifier.py`: Tests layer classification rules across file extensions and keywords.
- `backend/tests/test_architecture_graph_builder.py`: Tests graph generation, edge synthesis, and layout coordinate assignment.
- `backend/tests/test_architecture_api.py`: Tests end-to-end repository upload, analysis, multi-view graph retrieval, and 403 access control.

**Full test suite pass rate: 104 passed in 122s.**
